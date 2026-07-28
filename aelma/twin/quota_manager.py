"""QuotaManager: commercial fishing quota tracking and catch management.

Tracks species-based quotas for Alaska commercial fishing, logs catch events,
validates against remaining quota, and provides analytics for quota management.

Supported species:
- Salmon: chinook, coho, sockeye, pink, chum
- Groundfish: halibut, cod, black_cod
- Shellfish: crab (king, snow, dungeness)

Record shape (one JSON object per line for quotas and catches)::

    {
      "kind": "species_quota",
      "species": "chinook",
      "total_limit_lb": 1000.0,
      "current_catch_lb": 50.0,
      "reserve_percent": 10.0,
      "quota_source": "IFQ",
      "expiry_date": "2026-12-31T23:59:59.000000+00:00",
      "_loggedAt": "2026-07-28T10:30:00.123456+00:00",
      "_seq": 0
    }

    {
      "kind": "catch_event",
      "catch_id": "20260728_103000_001",
      "species": "chinook",
      "weight_lb": 15.5,
      "lat": 57.0531,
      "lon": -135.3300,
      "timestamp_ns": 1753478400000000000,
      "gear_type": "purse_seine",
      "vessel_id": "US-AK-FVEILEEN-51",
      "crew_member": "captain",
      "released": false,
      "_loggedAt": "2026-07-28T10:30:00.123456+00:00",
      "_seq": 1
    }

Contracts:
- Append-only JSONL storage for quotas and catches
- Atomic quota updates (new records, not mutations)
- Catch deduction is automatic, validated against remaining quota
- Alerts generated at 80%, 90%, 95%, and 100% quota usage
- JSONL persistence with timestamps

Stdlib only, synchronous I/O (quota/catch operations are low-frequency).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("aelma.twin.quota_manager")

#: Record kind identifiers
KIND_QUOTA = "species_quota"
KIND_CATCH = "catch_event"

#: Valid species with common names
VALID_SPECIES = frozenset({
    "chinook",  # King salmon
    "coho",     # Silver salmon
    "sockeye",  # Red salmon
    "pink",     # Humpy salmon
    "chum",     # Dog salmon
    "halibut",
    "cod",      # Pacific cod
    "black_cod",  # Sablefish
    "crab",     # General crab category
    "king_crab",
    "snow_crab",
    "dungeness_crab",
})

#: Quota sources
QUOTA_SOURCES = frozenset({"IFQ", "CDQ", "community", "state", "federal"})

#: Alert thresholds (percentage of quota used)
ALERT_THRESHOLDS = [80.0, 90.0, 95.0, 100.0]

#: Maximum catch events retained in memory
MAX_CATCHES = 5000

#: Default reserve percentage (safety buffer)
DEFAULT_RESERVE_PERCENT = 10.0


def _utc_now_iso() -> str:
    """Get current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _now_ns() -> int:
    """Get current time as nanoseconds since epoch."""
    return time.time_ns()


def _generate_catch_id() -> str:
    """Generate a unique catch ID from timestamp and UUID."""
    now = datetime.now(timezone.utc)
    prefix = now.strftime("%Y%m%d_%H%M%S")
    unique = str(uuid.uuid4())[:8]
    return f"{prefix}_{unique}"


@dataclass
class SpeciesQuota:
    """Quota allocation for a single species."""

    species: str
    total_limit_lb: float
    current_catch_lb: float = 0.0
    reserve_percent: float = DEFAULT_RESERVE_PERCENT
    quota_source: str = "IFQ"
    expiry_date: str | None = None

    def __post_init__(self):
        """Validate quota parameters."""
        if self.species not in VALID_SPECIES:
            raise ValueError(
                f"Invalid species: {self.species}. "
                f"Must be one of {sorted(VALID_SPECIES)}"
            )
        if self.total_limit_lb <= 0:
            raise ValueError("total_limit_lb must be positive")
        if self.current_catch_lb < 0:
            raise ValueError("current_catch_lb cannot be negative")
        if not 0 <= self.reserve_percent <= 100:
            raise ValueError("reserve_percent must be between 0 and 100")
        if self.quota_source not in QUOTA_SOURCES:
            raise ValueError(
                f"Invalid quota_source: {self.quota_source}. "
                f"Must be one of {sorted(QUOTA_SOURCES)}"
            )
        if self.current_catch_lb > self.total_limit_lb:
            raise ValueError(
                f"current_catch_lb ({self.current_catch_lb}) cannot exceed "
                f"total_limit_lb ({self.total_limit_lb})"
            )

    def remaining_lb(self) -> float:
        """Calculate remaining quota including reserve."""
        return max(0.0, self.total_limit_lb - self.current_catch_lb)

    def usable_lb(self) -> float:
        """Calculate usable quota (excluding reserve)."""
        reserve = self.total_limit_lb * (self.reserve_percent / 100.0)
        return max(0.0, self.remaining_lb() - reserve)

    def percent_used(self) -> float:
        """Calculate percentage of quota used."""
        if self.total_limit_lb <= 0:
            return 0.0
        return (self.current_catch_lb / self.total_limit_lb) * 100.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "species": self.species,
            "total_limit_lb": self.total_limit_lb,
            "current_catch_lb": self.current_catch_lb,
            "reserve_percent": self.reserve_percent,
            "quota_source": self.quota_source,
            "expiry_date": self.expiry_date,
        }


@dataclass
class CatchEvent:
    """A single catch event."""

    catch_id: str
    species: str
    weight_lb: float
    lat: float
    lon: float
    timestamp_ns: int
    gear_type: str
    vessel_id: str
    crew_member: str | None = None
    released: bool = False
    release_reason: str | None = None

    def __post_init__(self):
        """Validate catch event parameters."""
        if self.species not in VALID_SPECIES:
            raise ValueError(
                f"Invalid species: {self.species}. "
                f"Must be one of {sorted(VALID_SPECIES)}"
            )
        if self.weight_lb <= 0:
            raise ValueError("weight_lb must be positive")
        if not -90.0 <= self.lat <= 90.0:
            raise ValueError(f"lat out of range: {self.lat}")
        if not -180.0 <= self.lon <= 180.0:
            raise ValueError(f"lon out of range: {self.lon}")
        if not isinstance(self.timestamp_ns, int) or self.timestamp_ns < 0:
            raise ValueError(f"timestamp_ns must be positive int: {self.timestamp_ns}")
        if not self.gear_type or not isinstance(self.gear_type, str):
            raise ValueError("gear_type must be a non-empty string")
        if not self.vessel_id or not isinstance(self.vessel_id, str):
            raise ValueError("vessel_id must be a non-empty string")
        if self.released and not self.release_reason:
            raise ValueError("release_reason required when released=True")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "catch_id": self.catch_id,
            "species": self.species,
            "weight_lb": self.weight_lb,
            "lat": self.lat,
            "lon": self.lon,
            "timestamp_ns": self.timestamp_ns,
            "gear_type": self.gear_type,
            "vessel_id": self.vessel_id,
            "crew_member": self.crew_member,
            "released": self.released,
            "release_reason": self.release_reason,
        }


class QuotaManager:
    """Manage fishing quotas and catch logging for commercial fishing.

    Parameters
    ----------
    storage_path:
        Base path for JSONL files. Quotas stored at {storage_path}/quota.jsonl,
        catches at {storage_path}/catch.jsonl. None disables persistence.
    vessel_id:
        Vessel identifier for catch events
    default_reserve_percent:
        Default reserve percentage for new quotas (safety buffer)

    Attributes
    ----------
    quotas: dict[str, SpeciesQuota]
        Current quota allocations by species
    catches: deque[CatchEvent]
        In-memory catch event history (most recent first)
    """

    def __init__(
        self,
        storage_path: str | Path | None = None,
        vessel_id: str = "US-AK-FVEILEEN-51",
        default_reserve_percent: float = DEFAULT_RESERVE_PERCENT,
    ) -> None:
        self.vessel_id = vessel_id
        self.default_reserve_percent = default_reserve_percent

        # Storage paths
        if storage_path is not None:
            self._base_path = Path(storage_path)
            self._quota_path = self._base_path / "quota.jsonl"
            self._catch_path = self._base_path / "catch.jsonl"
        else:
            self._base_path = None
            self._quota_path = None
            self._catch_path = None

        # In-memory state
        self.quotas: dict[str, SpeciesQuota] = {}
        self._catches: deque[CatchEvent] = deque(maxlen=MAX_CATCHES)
        self._alerts: list[dict[str, Any]] = []

        # Sequence numbers for JSONL
        self._quota_seq = 0
        self._catch_seq = 0

        # Track last alert levels to avoid duplicate alerts
        self._last_alert_levels: dict[str, float] = {}

        # Load from storage if available
        if self._base_path is not None:
            self._load_quotas()
            self._load_catches()

    # ------------------------------------------------------------------ #
    # Quota management
    # ------------------------------------------------------------------ #

    def set_species_quota(
        self,
        species: str,
        total_limit_lb: float,
        current_catch_lb: float = 0.0,
        reserve_percent: float | None = None,
        quota_source: str = "IFQ",
        expiry_date: str | None = None,
    ) -> SpeciesQuota:
        """Set or update quota for a species.

        Creates a new quota record or replaces the existing one.

        Parameters
        ----------
        species:
            Species code (chinook, coho, halibut, etc.)
        total_limit_lb:
            Total quota limit in pounds
        current_catch_lb:
            Current catch amount (for existing quotas)
        reserve_percent:
            Safety buffer percentage (None for default)
        quota_source:
            Quota source (IFQ, CDQ, community, state, federal)
        expiry_date:
            ISO 8601 expiry date or None

        Returns
        -------
        SpeciesQuota
            The created or updated quota object
        """
        if reserve_percent is None:
            reserve_percent = self.default_reserve_percent

        quota = SpeciesQuota(
            species=species,
            total_limit_lb=float(total_limit_lb),
            current_catch_lb=float(current_catch_lb),
            reserve_percent=float(reserve_percent),
            quota_source=quota_source,
            expiry_date=expiry_date,
        )

        self.quotas[species] = quota
        self._append_quota(quota)
        return quota

    def get_species_quota(self, species: str) -> SpeciesQuota | None:
        """Get quota for a species, or None if not set."""
        return self.quotas.get(species)

    def get_all_quotas(self) -> dict[str, SpeciesQuota]:
        """Get all quota allocations."""
        return dict(self.quotas)

    def update_species_quota(
        self,
        species: str,
        total_limit_lb: float | None = None,
        current_catch_lb: float | None = None,
        reserve_percent: float | None = None,
        expiry_date: str | None = None,
    ) -> SpeciesQuota | None:
        """Update an existing quota allocation.

        Only updates fields that are not None. Returns None if species
        quota does not exist.

        Parameters
        ----------
        species:
            Species code to update
        total_limit_lb:
            New total limit (None to keep current)
        current_catch_lb:
            New current catch (None to keep current)
        reserve_percent:
            New reserve percentage (None to keep current)
        expiry_date:
            New expiry date (None to keep current)

        Returns
        -------
        SpeciesQuota | None
            Updated quota or None if species not found
        """
        existing = self.quotas.get(species)
        if existing is None:
            return None

        # Create new quota with updated values
        quota = SpeciesQuota(
            species=species,
            total_limit_lb=float(total_limit_lb) if total_limit_lb is not None else existing.total_limit_lb,
            current_catch_lb=float(current_catch_lb) if current_catch_lb is not None else existing.current_catch_lb,
            reserve_percent=float(reserve_percent) if reserve_percent is not None else existing.reserve_percent,
            quota_source=existing.quota_source,
            expiry_date=expiry_date if expiry_date is not None else existing.expiry_date,
        )

        self.quotas[species] = quota
        self._append_quota(quota)
        return quota

    def remove_species_quota(self, species: str) -> bool:
        """Remove quota for a species. Returns True if existed."""
        if species in self.quotas:
            del self.quotas[species]
            return True
        return False

    def transfer_quota(
        self,
        from_vessel: str,
        to_vessel: str,
        species: str,
        amount_lb: float,
    ) -> dict[str, Any]:
        """Record a quota transfer between vessels.

        Note: This creates a log entry only. Actual quota modification
        must be done separately via update_species_quota.

        Parameters
        ----------
        from_vessel:
            Source vessel ID
        to_vessel:
            Destination vessel ID
        species:
            Species code
        amount_lb:
            Amount to transfer

        Returns
        -------
        dict
            Transfer record
        """
        if amount_lb <= 0:
            raise ValueError("amount_lb must be positive")

        transfer = {
            "kind": "quota_transfer",
            "from_vessel": from_vessel,
            "to_vessel": to_vessel,
            "species": species,
            "amount_lb": float(amount_lb),
            "timestamp_ns": _now_ns(),
            "ts": _utc_now_iso(),
        }

        # Log transfer to catch file for audit trail
        if self._catch_path is not None:
            self._base_path.parent.mkdir(parents=True, exist_ok=True)
            with self._catch_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(transfer, separators=(",", ":")) + "\n")

        return transfer

    # ------------------------------------------------------------------ #
    # Catch logging
    # ------------------------------------------------------------------ #

    def log_catch(
        self,
        species: str,
        weight_lb: float,
        lat: float,
        lon: float,
        gear_type: str,
        timestamp_ns: int | None = None,
        crew_member: str | None = None,
    ) -> CatchEvent:
        """Log a catch event and deduct from quota.

        Parameters
        ----------
        species:
            Species code
        weight_lb:
            Weight in pounds
        lat:
            Latitude
        lon:
            Longitude
        gear_type:
            Gear type (purse_seine, gillnet, pot, longline, etc.)
        timestamp_ns:
            Timestamp in nanoseconds (None for now)
        crew_member:
            Crew member identifier

        Returns
        -------
        CatchEvent
            The logged catch event

        Raises
        ------
        ValueError
            If species quota doesn't exist or insufficient quota
        """
        quota = self.quotas.get(species)
        if quota is None:
            raise ValueError(f"No quota set for species: {species}")

        # Check against usable quota (including reserve)
        if weight_lb > quota.usable_lb():
            raise ValueError(
                f"Insufficient quota for {species}: "
                f"requesting {weight_lb} lb, "
                f"usable {quota.usable_lb():.2f} lb "
                f"(remaining {quota.remaining_lb():.2f} lb)"
            )

        # Create catch event
        catch = CatchEvent(
            catch_id=_generate_catch_id(),
            species=species,
            weight_lb=float(weight_lb),
            lat=float(lat),
            lon=float(lon),
            timestamp_ns=int(timestamp_ns) if timestamp_ns is not None else _now_ns(),
            gear_type=gear_type,
            vessel_id=self.vessel_id,
            crew_member=crew_member,
        )

        # Deduct from quota
        quota.current_catch_lb += catch.weight_lb

        # Store catch event
        self._catches.appendleft(catch)
        self._append_catch(catch)

        # Check for alerts
        self._check_quota_alerts(species)

        return catch

    def log_release(
        self,
        catch_id: str,
        reason: str,
    ) -> CatchEvent | None:
        """Mark a catch as released and restore quota.

        Parameters
        ----------
        catch_id:
            Catch event ID
        reason:
            Release reason (size_limit, bycatch, quality, etc.)

        Returns
        -------
        CatchEvent | None
            Updated catch event or None if not found
        """
        # Find catch event
        catch = None
        for c in self._catches:
            if c.catch_id == catch_id:
                catch = c
                break

        if catch is None:
            return None

        if catch.released:
            return catch  # Already released

        # Update catch event
        catch.released = True
        catch.release_reason = reason

        # Restore quota
        quota = self.quotas.get(catch.species)
        if quota is not None:
            quota.current_catch_lb = max(0.0, quota.current_catch_lb - catch.weight_lb)

        # Log updated catch
        self._append_catch(catch)

        return catch

    def get_catch_history(
        self,
        species: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1000,
    ) -> list[CatchEvent]:
        """Get catch history with optional filters.

        Parameters
        ----------
        species:
            Filter by species code (None for all)
        start_time:
            Start timestamp in nanoseconds (None for beginning)
        end_time:
            End timestamp in nanoseconds (None for now)
        limit:
            Maximum number of events to return

        Returns
        -------
        list[CatchEvent]
            Filtered catch events, most recent first
        """
        results: list[CatchEvent] = []

        for catch in self._catches:
            if species is not None and catch.species != species:
                continue
            if start_time is not None and catch.timestamp_ns < start_time:
                continue
            if end_time is not None and catch.timestamp_ns > end_time:
                continue
            results.append(catch)
            if len(results) >= limit:
                break

        return results

    # ------------------------------------------------------------------ #
    # Quota queries
    # ------------------------------------------------------------------ #

    def get_remaining_quota(self, species: str) -> float:
        """Get remaining quota for a species.

        Returns 0.0 if species quota not set.
        """
        quota = self.quotas.get(species)
        return quota.remaining_lb() if quota else 0.0

    def get_quota_percent_used(self, species: str) -> float:
        """Get percentage of quota used for a species.

        Returns 0.0 if species quota not set.
        """
        quota = self.quotas.get(species)
        return quota.percent_used() if quota else 0.0

    def get_quota_status(self) -> dict[str, dict[str, Any]]:
        """Get comprehensive quota status for all species.

        Returns
        -------
        dict
            Status dict keyed by species with details:
            - total_limit_lb: Total quota limit
            - current_catch_lb: Current catch
            - remaining_lb: Remaining quota
            - usable_lb: Usable quota (excluding reserve)
            - percent_used: Percentage used
            - reserve_percent: Reserve percentage
            - quota_source: Quota source
            - expiry_date: Expiry date
        """
        status: dict[str, dict[str, Any]] = {}

        for species, quota in self.quotas.items():
            status[species] = {
                "total_limit_lb": quota.total_limit_lb,
                "current_catch_lb": quota.current_catch_lb,
                "remaining_lb": quota.remaining_lb(),
                "usable_lb": quota.usable_lb(),
                "percent_used": quota.percent_used(),
                "reserve_percent": quota.reserve_percent,
                "quota_source": quota.quota_source,
                "expiry_date": quota.expiry_date,
            }

        return status

    def check_quota_available(
        self,
        species: str,
        weight_lb: float,
    ) -> bool:
        """Check if sufficient quota is available for a catch.

        Returns False if species quota not set or insufficient quota.
        """
        quota = self.quotas.get(species)
        if quota is None:
            return False
        return weight_lb <= quota.usable_lb()

    # ------------------------------------------------------------------ #
    # Analytics
    # ------------------------------------------------------------------ #

    def calculate_catch_rate(
        self,
        species: str,
        window_hours: float = 24.0,
    ) -> float:
        """Calculate catch rate for a species over a time window.

        Parameters
        ----------
        species:
            Species code
        window_hours:
            Time window in hours (default 24)

        Returns
        -------
        float
            Catch rate in pounds per hour
        """
        now = _now_ns()
        window_ns = int(window_hours * 3600_000_000_000)  # hours to nanoseconds
        start_ns = now - window_ns

        total_catch = 0.0
        for catch in self._catches:
            if catch.species == species and not catch.released:
                if catch.timestamp_ns >= start_ns:
                    total_catch += catch.weight_lb

        return total_catch / window_hours if window_hours > 0 else 0.0

    def project_exhaustion_date(
        self,
        species: str,
        window_hours: float = 24.0,
    ) -> str | None:
        """Project when quota will be exhausted based on recent catch rate.

        Parameters
        ----------
        species:
            Species code
        window_hours:
            Time window for catch rate calculation (default 24)

        Returns
        -------
        str | None
            ISO 8601 projection date or None if not calculable
        """
        quota = self.quotas.get(species)
        if quota is None:
            return None

        remaining = quota.usable_lb()
        if remaining <= 0:
            return _utc_now_iso()  # Already exhausted

        rate = self.calculate_catch_rate(species, window_hours)
        if rate <= 0:
            return None  # No recent catch, can't project

        hours_until_exhaustion = remaining / rate
        seconds = int(hours_until_exhaustion * 3600)

        projection = datetime.now(timezone.utc)
        projection = projection.fromtimestamp(
            projection.timestamp() + seconds,
            tz=timezone.utc,
        )

        return projection.isoformat()

    def get_bycatch_report(
        self,
        target_species: str,
    ) -> dict[str, float]:
        """Report bycatch ratios for a target species.

        Parameters
        ----------
        target_species:
            Primary species to analyze

        Returns
        -------
        dict
            Bycatch dict with species as keys and pounds as values
        """
        bycatch: dict[str, float] = {}

        for catch in self._catches:
            if catch.released:
                continue
            if catch.species != target_species:
                bycatch[catch.species] = bycatch.get(catch.species, 0.0) + catch.weight_lb

        return bycatch

    def get_species_summary(
        self,
        species: str,
    ) -> dict[str, Any]:
        """Get comprehensive summary for a single species.

        Parameters
        ----------
        species:
            Species code

        Returns
        -------
        dict
            Summary with quota status, catch count, catch rate,
            exhaustion projection, and bycatch
        """
        quota = self.quotas.get(species)
        if quota is None:
            return {
                "species": species,
                "quota_set": False,
            }

        # Count catch events
        catch_count = sum(
            1 for c in self._catches
            if c.species == species and not c.released
        )

        # Calculate catch rate
        catch_rate = self.calculate_catch_rate(species)

        # Project exhaustion
        exhaustion = self.project_exhaustion_date(species)

        return {
            "species": species,
            "quota_set": True,
            "total_limit_lb": quota.total_limit_lb,
            "current_catch_lb": quota.current_catch_lb,
            "remaining_lb": quota.remaining_lb(),
            "usable_lb": quota.usable_lb(),
            "percent_used": quota.percent_used(),
            "catch_count": catch_count,
            "catch_rate_lb_per_hour": round(catch_rate, 2),
            "projected_exhaustion": exhaustion,
            "quota_source": quota.quota_source,
            "expiry_date": quota.expiry_date,
        }

    # ------------------------------------------------------------------ #
    # Alerts
    # ------------------------------------------------------------------ #

    def _check_quota_alerts(self, species: str) -> list[dict[str, Any]]:
        """Check and generate quota threshold alerts."""
        quota = self.quotas.get(species)
        if quota is None:
            return []

        percent = quota.percent_used()
        last_level = self._last_alert_levels.get(species, 0.0)
        new_alerts: list[dict[str, Any]] = []

        for threshold in ALERT_THRESHOLDS:
            if percent >= threshold and last_level < threshold:
                alert = {
                    "kind": "quota_alert",
                    "species": species,
                    "threshold": threshold,
                    "percent_used": round(percent, 2),
                    "remaining_lb": round(quota.remaining_lb(), 2),
                    "timestamp_ns": _now_ns(),
                    "ts": _utc_now_iso(),
                }
                new_alerts.append(alert)
                self._alerts.append(alert)

        # Update last alert level
        if percent > last_level:
            self._last_alert_levels[species] = percent

        return new_alerts

    def get_alerts(
        self,
        species: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent alerts, optionally filtered by species.

        Parameters
        ----------
        species:
            Filter by species (None for all)
        limit:
            Maximum alerts to return

        Returns
        -------
        list[dict]
            Alert events, most recent first
        """
        filtered = self._alerts
        if species is not None:
            filtered = [a for a in self._alerts if a.get("species") == species]

        return filtered[:limit]

    # ------------------------------------------------------------------ #
    # Integration
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        """Export quota manager state to dictionary."""
        return {
            "vessel_id": self.vessel_id,
            "quotas": {
                species: quota.to_dict()
                for species, quota in self.quotas.items()
            },
            "catch_count": len(self._catches),
            "alert_count": len(self._alerts),
        }

    def get_watcher_frame(self) -> dict[str, Any]:
        """Get frame data for WatcherRegistry evaluation.

        Returns a flat dict with quota metrics for rule evaluation.

        Example frame data::

            {
                "quota_chinook_percent_used": 45.2,
                "quota_chinook_remaining_lb": 548.0,
                "quota_halibut_percent_used": 92.1,
                "quota_halibut_remaining_lb": 79.0,
                "quota_alert_count": 2,
                "quota_catch_rate_chinook_lb_per_hr": 12.5,
            }
        """
        frame: dict[str, Any] = {
            "quota_alert_count": len(self._alerts),
        }

        for species, quota in self.quotas.items():
            prefix = f"quota_{species}"
            frame[f"{prefix}_percent_used"] = quota.percent_used()
            frame[f"{prefix}_remaining_lb"] = quota.remaining_lb()
            frame[f"{prefix}_usable_lb"] = quota.usable_lb()
            frame[f"{prefix}_total_limit_lb"] = quota.total_limit_lb
            frame[f"{prefix}_current_catch_lb"] = quota.current_catch_lb

        # Add catch rates
        for species in self.quotas.keys():
            rate = self.calculate_catch_rate(species, 24.0)
            frame[f"quota_catch_rate_{species}_lb_per_hr"] = round(rate, 2)

        return frame

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _append_quota(self, quota: SpeciesQuota) -> None:
        """Append quota record to JSONL file."""
        if self._quota_path is None:
            return

        self._base_path.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "kind": KIND_QUOTA,
            **quota.to_dict(),
            "_loggedAt": _utc_now_iso(),
            "_seq": self._quota_seq,
        }

        with self._quota_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")

        self._quota_seq += 1

    def _append_catch(self, catch: CatchEvent) -> None:
        """Append catch record to JSONL file."""
        if self._catch_path is None:
            return

        self._base_path.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "kind": KIND_CATCH,
            **catch.to_dict(),
            "_loggedAt": _utc_now_iso(),
            "_seq": self._catch_seq,
        }

        with self._catch_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")

        self._catch_seq += 1

    def _load_quotas(self) -> None:
        """Load quota records from JSONL file."""
        if self._quota_path is None or not self._quota_path.exists():
            return

        max_seq = -1
        with self._quota_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    log.warning("Skipping malformed quota line in %s", self._quota_path)
                    continue

                if record.get("kind") != KIND_QUOTA:
                    continue

                try:
                    quota = SpeciesQuota(
                        species=record["species"],
                        total_limit_lb=record["total_limit_lb"],
                        current_catch_lb=record.get("current_catch_lb", 0.0),
                        reserve_percent=record.get("reserve_percent", DEFAULT_RESERVE_PERCENT),
                        quota_source=record.get("quota_source", "IFQ"),
                        expiry_date=record.get("expiry_date"),
                    )
                    self.quotas[quota.species] = quota

                    seq = record.get("_seq", -1)
                    if isinstance(seq, int) and seq > max_seq:
                        max_seq = seq
                except (KeyError, ValueError, TypeError) as exc:
                    log.warning("Skipping invalid quota record: %s", exc)
                    continue

        self._quota_seq = max_seq + 1
        log.info("Loaded %d quota allocations from %s", len(self.quotas), self._quota_path)

    def _load_catches(self) -> None:
        """Load catch records from JSONL file."""
        if self._catch_path is None or not self._catch_path.exists():
            return

        max_seq = -1
        with self._catch_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    log.warning("Skipping malformed catch line in %s", self._catch_path)
                    continue

                kind = record.get("kind")
                if kind == KIND_CATCH:
                    try:
                        catch = CatchEvent(
                            catch_id=record["catch_id"],
                            species=record["species"],
                            weight_lb=record["weight_lb"],
                            lat=record["lat"],
                            lon=record["lon"],
                            timestamp_ns=record["timestamp_ns"],
                            gear_type=record["gear_type"],
                            vessel_id=record["vessel_id"],
                            crew_member=record.get("crew_member"),
                            released=record.get("released", False),
                            release_reason=record.get("release_reason"),
                        )
                        self._catches.appendleft(catch)

                        seq = record.get("_seq", -1)
                        if isinstance(seq, int) and seq > max_seq:
                            max_seq = seq
                    except (KeyError, ValueError, TypeError) as exc:
                        log.warning("Skipping invalid catch record: %s", exc)
                        continue
                elif kind == "quota_transfer":
                    # Transfer records are logged but not loaded
                    pass
                elif kind == "quota_alert":
                    # Load alerts
                    self._alerts.append(record)

                    seq = record.get("_seq", -1)
                    if isinstance(seq, int) and seq > max_seq:
                        max_seq = seq

        self._catch_seq = max_seq + 1
        log.info("Loaded %d catch events from %s", len(self._catches), self._catch_path)

    def save(self) -> None:
        """Force save all pending data (flush if needed)."""
        # Data is flushed on every append, so this is a no-op
        # Kept for API compatibility
        pass

    async def close(self) -> None:
        """Cleanup (no-op for sync implementation)."""
        pass


__all__ = [
    "QuotaManager",
    "SpeciesQuota",
    "CatchEvent",
    "VALID_SPECIES",
    "QUOTA_SOURCES",
    "ALERT_THRESHOLDS",
]
