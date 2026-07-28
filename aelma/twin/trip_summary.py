"""TripSummary: end-of-trip report generator for AELMA.

Aggregates the three twin data sources — telemetry packets
(:mod:`schema/telemetry_packet.schema.json`), the A2A action log
(:mod:`twin.a2a_log`), and the crew operations log (:mod:`twin.oplog`) —
into a single trip summary: distance traveled, max depth, fishing time,
alerts fired, crew actions, and catch statistics.

The collector is feed-based: the caller pumps records in via
:meth:`TripSummary.add_telemetry`, :meth:`TripSummary.add_oplog_entry`, and
:meth:`TripSummary.add_a2a_action` (live, or replayed from the JSONL logs),
then calls :meth:`TripSummary.generate_summary` for the aggregate dict and
one of the exporters for JSON / HTML / PDF-like text output.

Stdlib only.
"""

from __future__ import annotations

import html
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .state import haversine_m

log = logging.getLogger("aelma.twin.trip_summary")

# Telemetry channels consumed by the summary.
LAT_CHANNEL = "position.lat"
LON_CHANNEL = "position.lon"
DEPTH_CHANNEL = "depth_m"

# A2A action name that watcher rules fire for alerts (see twin.watchers).
ALERT_ACTION = "raise_alert"

_M_PER_NM = 1852.0
_M_PER_KM = 1000.0

# OpLog entry types that bracket "fishing time", in priority order. Gear in
# the water is the primary definition; haul brackets are the fallback.
_GEAR_OPEN = "gear_deployed"
_GEAR_CLOSE = "gear_retrieved"
_HAUL_OPEN = "haul_started"
_HAUL_CLOSE = "haul_complete"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: Any) -> datetime | None:
    """Coerce a timestamp to an aware UTC datetime.

    Accepts ``None``, a :class:`~datetime.datetime` (naive assumed UTC),
    epoch seconds, epoch nanoseconds (telemetry ``timestamp_ns``), or an
    ISO-8601 string. Returns ``None`` for anything unparseable — a summary
    must never crash on one bad record.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            # Nanosecond epochs are >= ~1e18 for modern dates; seconds ~1e9.
            seconds = value / 1e9 if value > 1e15 else float(value)
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _fmt_duration(seconds: float) -> str:
    """Render seconds as ``Xh YYm ZZs`` for the text/HTML reports."""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


class TripSummary:
    """Accumulates telemetry, OpLog, and A2A records for one trip.

    Parameters
    ----------
    vessel_id:
        Vessel identifier stamped onto the report header.
    """

    def __init__(self, vessel_id: str = "US-AK-FVEILEEN-51") -> None:
        self.vessel_id = vessel_id

        # Telemetry accumulators.
        self._fixes: list[tuple[datetime, float, float]] = []
        self._pending_lat: tuple[datetime, float] | None = None
        self._pending_lon: tuple[datetime, float] | None = None
        self._depths: list[tuple[datetime, float]] = []
        self._telemetry_ts: list[datetime] = []

        # Log accumulators (kept verbatim for the report's entry listings).
        self._oplog_entries: list[dict[str, Any]] = []
        self._a2a_actions: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_telemetry(self, packet: Mapping[str, Any]) -> None:
        """Consume one TelemetryPacket (see telemetry_packet.schema.json).

        Only ``position.lat`` / ``position.lon`` (distance) and ``depth_m``
        (max depth) channels affect the summary; other channels still extend
        the trip time window. Malformed packets are ignored with a warning.
        """
        if not isinstance(packet, Mapping):
            raise TypeError("TripSummary.add_telemetry: packet must be a mapping")
        ts = _parse_ts(packet.get("timestamp_ns"))
        channel = packet.get("channel")
        value = packet.get("value")
        if ts is not None:
            self._telemetry_ts.append(ts)
        if ts is None or not isinstance(value, (int, float)) or isinstance(value, bool):
            return

        if channel == LAT_CHANNEL:
            self._pending_lat = (ts, float(value))
            self._maybe_fix()
        elif channel == LON_CHANNEL:
            self._pending_lon = (ts, float(value))
            self._maybe_fix()
        elif channel == DEPTH_CHANNEL:
            self._depths.append((ts, float(value)))

    def _maybe_fix(self) -> None:
        """Emit a position fix when both lat and lon are pending.

        The bridge emits lat/lon as separate packets with the same
        timestamp; fixes pair on that timestamp (mirrors VesselState).
        Unpaired components stay pending so a later matching packet can
        still complete the fix.
        """
        if self._pending_lat is None or self._pending_lon is None:
            return
        (lat_ts, lat), (lon_ts, lon) = self._pending_lat, self._pending_lon
        if lat_ts == lon_ts:
            self._fixes.append((lat_ts, lat, lon))
            self._pending_lat = None
            self._pending_lon = None

    def add_oplog_entry(self, entry: Mapping[str, Any]) -> None:
        """Consume one OpLog record (see :mod:`twin.oplog` for the shape)."""
        if not isinstance(entry, Mapping):
            raise TypeError("TripSummary.add_oplog_entry: entry must be a mapping")
        self._oplog_entries.append(dict(entry))

    def add_a2a_action(self, action: Mapping[str, Any]) -> None:
        """Consume one A2ALog record (see :mod:`twin.a2a_log` for the shape)."""
        if not isinstance(action, Mapping):
            raise TypeError("TripSummary.add_a2a_action: action must be a mapping")
        self._a2a_actions.append(dict(action))

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _distance_m(self) -> float:
        total = 0.0
        for (_, lat1, lon1), (_, lat2, lon2) in zip(self._fixes, self._fixes[1:]):
            total += haversine_m(lat1, lon1, lat2, lon2)
        return total

    def _trip_window(self) -> tuple[datetime | None, datetime | None]:
        stamps: list[datetime] = list(self._telemetry_ts)
        for entry in self._oplog_entries:
            ts = _parse_ts(entry.get("ts"))
            if ts is not None:
                stamps.append(ts)
        for action in self._a2a_actions:
            ts = _parse_ts(action.get("ts"))
            if ts is not None:
                stamps.append(ts)
        if not stamps:
            return None, None
        return min(stamps), max(stamps)

    def _fishing_time_s(self, trip_end: datetime | None) -> tuple[float, str]:
        """Total time with gear in the water, in seconds.

        Pairs ``gear_deployed`` → ``gear_retrieved`` in chronological order;
        a trailing unmatched deployment runs to the trip end. Falls back to
        ``haul_started`` → ``haul_complete`` when no gear events exist.
        Returns ``(seconds, basis)`` where basis names the bracket used.
        """
        for open_type, close_type, basis in (
            (_GEAR_OPEN, _GEAR_CLOSE, "gear_in_water"),
            (_HAUL_OPEN, _HAUL_CLOSE, "hauls"),
        ):
            events = sorted(
                (
                    (_parse_ts(e.get("ts")), e.get("entry_type"))
                    for e in self._oplog_entries
                    if e.get("entry_type") in (open_type, close_type)
                ),
                key=lambda item: (item[0] is None, item[0]),
            )
            events = [(ts, kind) for ts, kind in events if ts is not None]
            if not events:
                continue
            total = 0.0
            open_ts: datetime | None = None
            for ts, kind in events:
                if kind == open_type and open_ts is None:
                    open_ts = ts
                elif kind == close_type and open_ts is not None:
                    total += max(0.0, (ts - open_ts).total_seconds())
                    open_ts = None
            if open_ts is not None and trip_end is not None and trip_end > open_ts:
                total += (trip_end - open_ts).total_seconds()
            return total, basis
        return 0.0, "none"

    def _catch_statistics(self) -> dict[str, Any]:
        """Aggregate ``catch_logged`` OpLog entries by species."""
        by_species: dict[str, dict[str, float]] = {}
        total_count = 0.0
        total_weight = 0.0
        entries = 0
        for entry in self._oplog_entries:
            if entry.get("entry_type") != "catch_logged":
                continue
            entries += 1
            meta = entry.get("metadata") or {}
            if not isinstance(meta, Mapping):
                meta = {}
            species = str(meta.get("species") or "unknown")
            bucket = by_species.setdefault(species, {"count": 0.0, "weight_kg": 0.0})
            count = meta.get("count")
            weight = meta.get("weight_kg")
            if isinstance(count, (int, float)) and not isinstance(count, bool):
                bucket["count"] += count
                total_count += count
            if isinstance(weight, (int, float)) and not isinstance(weight, bool):
                bucket["weight_kg"] += weight
                total_weight += weight
        return {
            "entries": entries,
            "total_count": total_count,
            "total_weight_kg": round(total_weight, 3),
            "by_species": {
                name: {"count": b["count"], "weight_kg": round(b["weight_kg"], 3)}
                for name, b in sorted(by_species.items())
            },
        }

    def generate_summary(self) -> dict[str, Any]:
        """Compute the aggregate trip summary as a plain dict."""
        start, end = self._trip_window()
        duration_s = (end - start).total_seconds() if start and end else 0.0
        distance_m = self._distance_m()
        fishing_s, fishing_basis = self._fishing_time_s(end)

        alerts = [a for a in self._a2a_actions if a.get("action") == ALERT_ACTION]
        alerts_by_kind: dict[str, int] = {}
        for alert in alerts:
            payload = alert.get("payload") or {}
            kind = str(payload.get("kind", "unknown")) if isinstance(payload, Mapping) else "unknown"
            alerts_by_kind[kind] = alerts_by_kind.get(kind, 0) + 1

        a2a_by_action: dict[str, int] = {}
        a2a_by_source: dict[str, int] = {}
        for action in self._a2a_actions:
            name = str(action.get("action", "unknown"))
            a2a_by_action[name] = a2a_by_action.get(name, 0) + 1
            source = str(action.get("source", "unknown"))
            a2a_by_source[source] = a2a_by_source.get(source, 0) + 1

        crew_by_type: dict[str, int] = {}
        for entry in self._oplog_entries:
            kind = str(entry.get("entry_type", "unknown"))
            crew_by_type[kind] = crew_by_type.get(kind, 0) + 1

        depths = [d for _, d in self._depths]
        hauls = sum(1 for e in self._oplog_entries if e.get("entry_type") == _HAUL_CLOSE)

        return {
            "vessel_id": self.vessel_id,
            "generated_at": _utc_now_iso(),
            "trip_window": {
                "start": _iso(start),
                "end": _iso(end),
                "duration_s": round(duration_s, 3),
            },
            "distance": {
                "m": round(distance_m, 1),
                "km": round(distance_m / _M_PER_KM, 3),
                "nm": round(distance_m / _M_PER_NM, 3),
                "position_fixes": len(self._fixes),
            },
            "depth": {
                "max_m": max(depths) if depths else None,
                "min_m": min(depths) if depths else None,
                "samples": len(depths),
            },
            "fishing": {
                "time_s": round(fishing_s, 3),
                "basis": fishing_basis,
                "gear_deployments": crew_by_type.get(_GEAR_OPEN, 0),
                "hauls_completed": hauls,
            },
            "alerts": {
                "total": len(alerts),
                "by_kind": dict(sorted(alerts_by_kind.items())),
                "entries": [
                    {
                        "ts": a.get("ts"),
                        "kind": (a.get("payload") or {}).get("kind")
                        if isinstance(a.get("payload"), Mapping)
                        else None,
                        "reason": a.get("reason", ""),
                        "priority": a.get("priority"),
                        "source": a.get("source"),
                    }
                    for a in alerts
                ],
            },
            "a2a_actions": {
                "total": len(self._a2a_actions),
                "by_action": dict(sorted(a2a_by_action.items())),
                "by_source": dict(sorted(a2a_by_source.items())),
            },
            "crew_actions": {
                "total": len(self._oplog_entries),
                "by_type": dict(sorted(crew_by_type.items())),
                "entries": [
                    {
                        "ts": e.get("ts"),
                        "entry_type": e.get("entry_type"),
                        "crew": e.get("crew"),
                        "message": e.get("message", ""),
                    }
                    for e in self._oplog_entries
                ],
            },
            "catch": self._catch_statistics(),
        }

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_json(self, summary: Mapping[str, Any] | None = None, *, indent: int = 2) -> str:
        """Serialize the summary to JSON."""
        if summary is None:
            summary = self.generate_summary()
        return json.dumps(summary, indent=indent, ensure_ascii=False, default=str)

    def export_text(self, summary: Mapping[str, Any] | None = None) -> str:
        """Render a PDF-like plain-text report (fixed-width sections).

        Suitable for printing or piping through a text-to-PDF tool.
        """
        if summary is None:
            summary = self.generate_summary()
        s = summary
        rule = "=" * 64
        thin = "-" * 64
        window = s["trip_window"]
        lines = [
            rule,
            "AELMA TRIP SUMMARY REPORT".center(64),
            rule,
            f"Vessel:        {s['vessel_id']}",
            f"Generated:     {s['generated_at']}",
            f"Trip start:    {window['start'] or 'n/a'}",
            f"Trip end:      {window['end'] or 'n/a'}",
            f"Trip duration: {_fmt_duration(window['duration_s'])}",
            "",
            "NAVIGATION",
            thin,
            f"Distance traveled: {s['distance']['nm']:.2f} nm "
            f"({s['distance']['km']:.2f} km) over {s['distance']['position_fixes']} fixes",
            f"Max depth:         {s['depth']['max_m'] if s['depth']['max_m'] is not None else 'n/a'} m",
            f"Min depth:         {s['depth']['min_m'] if s['depth']['min_m'] is not None else 'n/a'} m",
            "",
            "FISHING",
            thin,
            f"Fishing time:      {_fmt_duration(s['fishing']['time_s'])} ({s['fishing']['basis']})",
            f"Gear deployments:  {s['fishing']['gear_deployments']}",
            f"Hauls completed:   {s['fishing']['hauls_completed']}",
            "",
            "CATCH",
            thin,
            f"Catch entries:     {s['catch']['entries']}",
            f"Total count:       {s['catch']['total_count']:g}",
            f"Total weight:      {s['catch']['total_weight_kg']:g} kg",
        ]
        for species, stats in s["catch"]["by_species"].items():
            lines.append(
                f"  - {species}: {stats['count']:g} fish, {stats['weight_kg']:g} kg"
            )
        lines += [
            "",
            "ALERTS",
            thin,
            f"Alerts fired:      {s['alerts']['total']}",
        ]
        for kind, count in s["alerts"]["by_kind"].items():
            lines.append(f"  - {kind}: {count}")
        for alert in s["alerts"]["entries"]:
            lines.append(f"  [{alert['ts']}] {alert.get('kind') or '?'}: {alert['reason']}")
        lines += [
            "",
            "CREW ACTIONS",
            thin,
            f"OpLog entries:     {s['crew_actions']['total']}",
        ]
        for entry_type, count in s["crew_actions"]["by_type"].items():
            lines.append(f"  - {entry_type}: {count}")
        lines += [
            "",
            "A2A ACTIONS",
            thin,
            f"Total actions:     {s['a2a_actions']['total']}",
        ]
        for name, count in s["a2a_actions"]["by_action"].items():
            lines.append(f"  - {name}: {count}")
        lines.append(rule)
        return "\n".join(lines)

    def export_html(self, summary: Mapping[str, Any] | None = None) -> str:
        """Render the summary as a self-contained HTML report."""
        if summary is None:
            summary = self.generate_summary()
        s = summary
        e = html.escape

        def rows(items: list[tuple[str, Any]]) -> str:
            return "\n".join(
                f"<tr><th>{e(str(k))}</th><td>{e(str(v))}</td></tr>" for k, v in items
            )

        def li(items: list[str]) -> str:
            return "\n".join(f"<li>{e(item)}</li>" for item in items)

        window = s["trip_window"]
        catch_species = [
            f"{name}: {stats['count']:g} fish, {stats['weight_kg']:g} kg"
            for name, stats in s["catch"]["by_species"].items()
        ] or ["none"]
        alerts_list = [
            f"[{a['ts']}] {a.get('kind') or '?'}: {a['reason']}" for a in s["alerts"]["entries"]
        ] or ["none"]
        crew_list = [
            f"[{en['ts']}] {en['entry_type']} ({en['crew']}): {en['message']}"
            for en in s["crew_actions"]["entries"]
        ] or ["none"]
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AELMA Trip Summary — {e(s['vessel_id'])}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 720px; color: #1a1a1a; }}
h1 {{ border-bottom: 3px solid #14532d; padding-bottom: .3rem; }}
h2 {{ color: #14532d; margin-top: 1.6rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: .35rem .6rem; text-align: left; }}
th {{ background: #f0f7f0; width: 40%; }}
</style>
</head>
<body>
<h1>AELMA Trip Summary</h1>
<table>
{rows([
    ("Vessel", s["vessel_id"]),
    ("Generated", s["generated_at"]),
    ("Trip start", window["start"] or "n/a"),
    ("Trip end", window["end"] or "n/a"),
    ("Trip duration", _fmt_duration(window["duration_s"])),
])}
</table>

<h2>Navigation</h2>
<table>
{rows([
    ("Distance traveled", f"{s['distance']['nm']:.2f} nm ({s['distance']['km']:.2f} km)"),
    ("Position fixes", s["distance"]["position_fixes"]),
    ("Max depth", f"{s['depth']['max_m']} m" if s["depth"]["max_m"] is not None else "n/a"),
    ("Min depth", f"{s['depth']['min_m']} m" if s["depth"]["min_m"] is not None else "n/a"),
])}
</table>

<h2>Fishing</h2>
<table>
{rows([
    ("Fishing time", f"{_fmt_duration(s['fishing']['time_s'])} ({s['fishing']['basis']})"),
    ("Gear deployments", s["fishing"]["gear_deployments"]),
    ("Hauls completed", s["fishing"]["hauls_completed"]),
])}
</table>

<h2>Catch</h2>
<table>
{rows([
    ("Catch entries", s["catch"]["entries"]),
    ("Total count", f"{s['catch']['total_count']:g}"),
    ("Total weight", f"{s['catch']['total_weight_kg']:g} kg"),
])}
</table>
<ul>
{li(catch_species)}
</ul>

<h2>Alerts ({s['alerts']['total']})</h2>
<ul>
{li(alerts_list)}
</ul>

<h2>Crew Actions ({s['crew_actions']['total']})</h2>
<ul>
{li(crew_list)}
</ul>

<h2>A2A Actions ({s['a2a_actions']['total']})</h2>
<ul>
{li([f"{name}: {count}" for name, count in s["a2a_actions"]["by_action"].items()])}
</ul>
</body>
</html>
"""

    def export(self, path: str, fmt: str | None = None) -> str:
        """Write the summary to ``path``; return the rendered content.

        ``fmt`` is one of ``json`` / ``html`` / ``text``; inferred from the
        file extension when omitted (``.txt`` maps to ``text``).
        """
        target = Path(path)
        if fmt is None:
            fmt = {".json": "json", ".html": "html", ".htm": "html", ".txt": "text"}.get(
                target.suffix.lower(), "json"
            )
        renderers = {"json": self.export_json, "html": self.export_html, "text": self.export_text}
        if fmt not in renderers:
            raise ValueError(f"TripSummary.export: unknown format {fmt!r}")
        summary = self.generate_summary()
        content = renderers[fmt](summary)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return content
