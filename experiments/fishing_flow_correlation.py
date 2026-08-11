#!/usr/bin/env python3
"""
Fishing-Flow Correlation Engine
===============================
Correlates fleet friction/flow metrics with fishing outcomes.

The killer eval: does crew flow state predict catch per set?

This is the dataset only a working fisherman with an agent fleet can collect.

Data sources:
- Fleet friction: SWMIDI error_mask values over time (from slackwater-rust)
- Flow state: Φ (flow friction) from harmony-core
- Fishing outcomes: catch count per set, species breakdown, location

Usage:
    # Record a session
    python3 fishing_flow_correlation.py record --flow 0.82 --friction 0 \
        --catch 47 --species "sockeye:30,pink:17" --location "Cape Edgecumbe" \
        --duration 4.5 --crew 4

    # Analyze
    python3 fishing_flow_correlation.py analyze

    # Load existing data
    python3 fishing_flow_correlation.py load data.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ── Error mask dimension names (from flux-core) ──────────────────────

FRICTION_DIMENSIONS = [
    "SPATIAL",      # bit 0: position collision
    "TEMPORAL",     # bit 1: timing violation
    "SEMANTIC",     # bit 2: nonsensical output
    "SAFETY",       # bit 3: content safety flag
    "RESOURCE",     # bit 4: resource unavailable
    "TOPOLOGY",     # bit 5: connectivity issue
    "AUTHORITY",    # bit 6: permission denied
    "CONSISTENCY",  # bit 7: state inconsistency
]


@dataclass
class FishingSession:
    """One fishing session with its flow metrics."""
    flow_state: float           # Φ (phi) — 0.0 to 1.0, higher = more flow
    friction_mask: int          # 8-bit SWMIDI error mask
    catch_count: int            # total fish caught
    species: dict[str, int]     # species → count
    location: str               # fishing location
    duration_min: float         # session duration in minutes
    crew_size: int              # number of crew
    timestamp: str = ""         # ISO timestamp
    notes: str = ""             # optional field notes

    @property
    def catch_per_hour(self) -> float:
        """Catch rate normalized by time."""
        return self.catch_count / (self.duration_min / 60) if self.duration_min > 0 else 0

    @property
    def catch_per_crew_hour(self) -> float:
        """Catch rate normalized by crew and time."""
        return self.catch_count / ((self.duration_min / 60) * self.crew_size) if (self.duration_min > 0 and self.crew_size > 0) else 0

    @property
    def friction_count(self) -> int:
        """Number of friction dimensions active."""
        return bin(self.friction_mask).count("1")

    @property
    def is_flow(self) -> bool:
        """Whether this was a flow-state session."""
        return self.friction_mask == 0 and self.flow_state > 0.7

    @property
    def active_frictions(self) -> list[str]:
        """Names of active friction dimensions."""
        return [
            name for i, name in enumerate(FRICTION_DIMENSIONS)
            if self.friction_mask & (1 << i)
        ]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FishingSession":
        return cls(**data)


class FishingFlowCorrelator:
    """
    Correlates fleet friction/flow metrics with fishing outcomes.

    The fundamental question: does flow state (low friction, high Φ)
    predict better catch rates?

    This is a question only a working fishing operation with an agent
    fleet monitoring friction in real-time can answer.
    """

    def __init__(self):
        self.sessions: list[FishingSession] = []

    def record(self, session: FishingSession) -> None:
        """Record a fishing session."""
        self.sessions.append(session)

    def record_raw(
        self,
        flow_state: float,
        friction_mask: int,
        catch_count: int,
        species: dict[str, int] | None = None,
        location: str = "",
        duration_min: float = 0,
        crew_size: int = 1,
        notes: str = "",
    ) -> FishingSession:
        """Record a session with individual parameters."""
        session = FishingSession(
            flow_state=flow_state,
            friction_mask=friction_mask,
            catch_count=catch_count,
            species=species or {},
            location=location,
            duration_min=duration_min,
            crew_size=crew_size,
            timestamp=datetime.now().isoformat(),
            notes=notes,
        )
        self.record(session)
        return session

    def load(self, filepath: str | Path) -> None:
        """Load sessions from a JSON file."""
        data = json.loads(Path(filepath).read_text())
        for session_data in data.get("sessions", []):
            self.record(FishingSession.from_dict(session_data))

    def save(self, filepath: str | Path) -> None:
        """Save sessions to a JSON file."""
        data = {
            "sessions": [s.to_dict() for s in self.sessions],
            "metadata": {
                "count": len(self.sessions),
                "saved_at": datetime.now().isoformat(),
            },
        }
        Path(filepath).write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def correlate(self) -> dict:
        """
        Compute correlation between flow state and fishing outcomes.

        Returns comprehensive analysis including:
        - Pearson correlation between Φ and catch/hour
        - Flow vs non-flow session comparison
        - Per-friction-dimension impact
        - Predictive summary
        """
        if len(self.sessions) < 3:
            return {
                "status": "insufficient_data",
                "min_sessions": 3,
                "current_sessions": len(self.sessions),
                "message": "Need at least 3 sessions for correlation analysis."
            }

        results: dict = {}

        # Basic stats
        results["total_sessions"] = len(self.sessions)
        results["total_catch"] = sum(s.catch_count for s in self.sessions)
        results["total_hours"] = sum(s.duration_min for s in self.sessions) / 60
        results["avg_flow_state"] = sum(s.flow_state for s in self.sessions) / len(self.sessions)
        results["avg_catch_per_hour"] = sum(s.catch_per_hour for s in self.sessions) / len(self.sessions)

        # Pearson correlation
        if HAS_NUMPY:
            flow = np.array([s.flow_state for s in self.sessions])
            catch = np.array([s.catch_per_hour for s in self.sessions])

            if len(flow) > 1 and np.std(flow) > 0 and np.std(catch) > 0:
                correlation = float(np.corrcoef(flow, catch)[0, 1])
            else:
                correlation = 0.0

            results["pearson_correlation"] = correlation
            results["correlation_strength"] = self._strength_label(correlation)
        else:
            correlation = self._pearson_manual(
                [s.flow_state for s in self.sessions],
                [s.catch_per_hour for s in self.sessions],
            )
            results["pearson_correlation"] = correlation
            results["correlation_strength"] = self._strength_label(correlation)

        # Flow vs non-flow split
        flow_sessions = [s for s in self.sessions if s.is_flow]
        non_flow = [s for s in self.sessions if not s.is_flow]

        flow_avg = self._mean([s.catch_per_hour for s in flow_sessions]) if flow_sessions else 0
        non_flow_avg = self._mean([s.catch_per_hour for s in non_flow]) if non_flow else 0

        results["flow_sessions"] = len(flow_sessions)
        results["non_flow_sessions"] = len(non_flow)
        results["avg_catch_flow"] = flow_avg
        results["avg_catch_non_flow"] = non_flow_avg
        results["flow_advantage"] = flow_avg - non_flow_avg
        results["flow_advantage_pct"] = (
            ((flow_avg - non_flow_avg) / non_flow_avg * 100) if non_flow_avg > 0 else 0
        )

        if flow_avg > non_flow_avg:
            results["prediction"] = "Flow state IMPROVES catch rate"
        elif flow_avg < non_flow_avg:
            results["prediction"] = "Flow state does NOT improve catch rate"
        else:
            results["prediction"] = "No detectable difference"

        # Per-friction-dimension analysis
        friction_impacts = {}
        for i, name in enumerate(FRICTION_DIMENSIONS):
            bit = 1 << i
            with_friction = [s for s in self.sessions if s.friction_mask & bit]
            without = [s for s in self.sessions if not (s.friction_mask & bit)]

            if with_friction and without:
                avg_with = self._mean([s.catch_per_hour for s in with_friction])
                avg_without = self._mean([s.catch_per_hour for s in without])
                friction_impacts[name] = {
                    "sessions_with": len(with_friction),
                    "sessions_without": len(without),
                    "avg_catch_with": avg_with,
                    "avg_catch_without": avg_without,
                    "impact": avg_without - avg_with,  # positive = friction hurts
                }

        results["friction_impacts"] = friction_impacts

        # Species analysis (if we have species data)
        all_species: dict[str, list[float]] = defaultdict(list)
        for s in self.sessions:
            for species, count in s.species.items():
                rate = count / (s.duration_min / 60) if s.duration_min > 0 else 0
                all_species[species].append(rate)

        if all_species:
            results["species_analysis"] = {
                species: {
                    "avg_per_hour": self._mean(rates),
                    "sessions": len(rates),
                    "total": sum(int(r * 1) for r in rates),  # rough
                }
                for species, rates in sorted(all_species.items())
            }

        # Location analysis
        location_data: dict[str, list[float]] = defaultdict(list)
        for s in self.sessions:
            if s.location:
                location_data[s.location].append(s.catch_per_hour)

        if location_data:
            results["location_analysis"] = {
                loc: {
                    "sessions": len(rates),
                    "avg_catch_per_hour": self._mean(rates),
                    "best": max(rates),
                    "worst": min(rates),
                }
                for loc, rates in sorted(location_data.items())
            }

        return results

    def report(self) -> str:
        """Generate a human-readable report."""
        c = self.correlate()

        if c.get("status") == "insufficient_data":
            return f"Insufficient data: {c.get('current_sessions', 0)}/{c.get('min_sessions', 3)} sessions."

        lines = [
            "=" * 60,
            "FISHING-FLOW CORRELATION REPORT",
            "=" * 60,
            "",
            f"Sessions analyzed: {c['total_sessions']}",
            f"Total catch: {c['total_catch']} fish over {c['total_hours']:.1f} hours",
            f"Average flow state (Φ): {c['avg_flow_state']:.3f}",
            f"Average catch/hour: {c['avg_catch_per_hour']:.1f}",
            "",
            "-" * 40,
            "FLOW vs NON-FLOW",
            "-" * 40,
            f"Flow sessions:     {c['flow_sessions']}  avg {c['avg_catch_flow']:.1f} fish/hour",
            f"Non-flow sessions: {c['non_flow_sessions']}  avg {c['avg_catch_non_flow']:.1f} fish/hour",
            f"Flow advantage:    {c['flow_advantage']:+.1f} fish/hour ({c['flow_advantage_pct']:+.0f}%)",
            "",
            f"Prediction: {c['prediction']}",
            "",
            "-" * 40,
            "CORRELATION",
            "-" * 40,
            f"Pearson r(Φ, catch/hour) = {c['pearson_correlation']:.3f}  [{c['correlation_strength']}]",
            "",
        ]

        # Friction dimension impacts
        if c.get("friction_impacts"):
            lines.append("-" * 40)
            lines.append("FRICTION DIMENSION IMPACTS")
            lines.append("-" * 40)
            for name, impact in sorted(c["friction_impacts"].items(), key=lambda x: -x[1]["impact"]):
                lines.append(
                    f"  {name:15s}  impact: {impact['impact']:+6.1f}/hr  "
                    f"({impact['sessions_with']} sessions with)"
                )
            lines.append("")

        # Location summary
        if c.get("location_analysis"):
            lines.append("-" * 40)
            lines.append("BY LOCATION")
            lines.append("-" * 40)
            for loc, data in c["location_analysis"].items():
                lines.append(
                    f"  {loc:30s}  avg {data['avg_catch_per_hour']:6.1f}/hr  "
                    f"({data['sessions']} sessions)"
                )
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

    def _mean(self, values: list[float]) -> float:
        return sum(values) / len(values) if values else 0

    def _pearson_manual(self, x: list[float], y: list[float]) -> float:
        """Pearson correlation without numpy."""
        n = len(x)
        if n < 2:
            return 0.0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        den_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        den_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
        if den_x == 0 or den_y == 0:
            return 0.0
        return num / (den_x * den_y)

    def _strength_label(self, r: float) -> str:
        """Label for correlation strength."""
        a = abs(r)
        if a >= 0.7:
            return f"strong {'positive' if r > 0 else 'negative'}"
        elif a >= 0.4:
            return f"moderate {'positive' if r > 0 else 'negative'}"
        elif a >= 0.2:
            return f"weak {'positive' if r > 0 else 'negative'}"
        else:
            return "negligible"


# ── Sample data for testing ──────────────────────────────────────────

SAMPLE_SESSIONS = [
    FishingSession(
        flow_state=0.85, friction_mask=0x00,
        catch_count=47, species={"sockeye": 30, "pink": 17},
        location="Cape Edgecumbe", duration_min=240, crew_size=4,
        timestamp="2026-08-01T06:00:00",
        notes="Perfect morning. Fleet humming. Everything clicked.",
    ),
    FishingSession(
        flow_state=0.78, friction_mask=0x00,
        catch_count=42, species={"sockeye": 28, "pink": 14},
        location="Cape Edgecumbe", duration_min=220, crew_size=4,
        timestamp="2026-08-02T06:00:00",
        notes="Smooth operation, minor GPS glitch.",
    ),
    FishingSession(
        flow_state=0.45, friction_mask=0x12,  # RESOURCE + TOPOLOGY
        catch_count=18, species={"sockeye": 10, "pink": 8},
        location="Inner Bay", duration_min=200, crew_size=4,
        timestamp="2026-08-03T06:00:00",
        notes="Net sensor down, GPS laggy. Crew frustrated.",
    ),
    FishingSession(
        flow_state=0.91, friction_mask=0x00,
        catch_count=52, species={"sockeye": 35, "pink": 15, "chum": 2},
        location="Cape Edgecumbe", duration_min=260, crew_size=4,
        timestamp="2026-08-04T05:30:00",
        notes="Best morning all season. Everything in flow.",
    ),
    FishingSession(
        flow_state=0.38, friction_mask=0x16,  # SPATIAL + RESOURCE + TOPOLOGY
        catch_count=12, species={"pink": 12},
        location="South Pass", duration_min=180, crew_size=3,
        timestamp="2026-08-05T07:00:00",
        notes="Gear issues, short crew, bad position data.",
    ),
    FishingSession(
        flow_state=0.72, friction_mask=0x00,
        catch_count=35, species={"sockeye": 22, "pink": 13},
        location="Cape Edgecumbe", duration_min=210, crew_size=4,
        timestamp="2026-08-06T06:00:00",
        notes="Good steady morning, no friction events.",
    ),
    FishingSession(
        flow_state=0.62, friction_mask=0x02,  # TEMPORAL only
        catch_count=28, species={"sockeye": 18, "pink": 10},
        location="Inner Bay", duration_min=190, crew_size=4,
        timestamp="2026-08-07T06:30:00",
        notes="Slight timing issue with tide change, otherwise OK.",
    ),
    FishingSession(
        flow_state=0.88, friction_mask=0x00,
        catch_count=49, species={"sockeye": 31, "pink": 16, "coho": 2},
        location="Cape Edgecumbe", duration_min=250, crew_size=4,
        timestamp="2026-08-08T05:45:00",
        notes="Outstanding morning. Fleet coordination perfect.",
    ),
]


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fishing-Flow Correlation Engine — does flow state predict catch?"
    )
    sub = parser.add_subparsers(dest="command")

    # Record
    rec = sub.add_parser("record", help="Record a fishing session")
    rec.add_argument("--flow", type=float, required=True, help="Flow state Φ (0-1)")
    rec.add_argument("--friction", type=int, required=True, help="Friction bitmask (0-255)")
    rec.add_argument("--catch", type=int, required=True, help="Total catch count")
    rec.add_argument("--species", type=str, default="", help="Species breakdown: sockeye:30,pink:17")
    rec.add_argument("--location", type=str, default="", help="Fishing location")
    rec.add_argument("--duration", type=float, required=True, help="Duration in minutes")
    rec.add_argument("--crew", type=int, default=1, help="Crew size")
    rec.add_argument("--notes", type=str, default="", help="Field notes")
    rec.add_argument("--data-file", type=str, default="fishing_flow_data.json", help="Data file path")

    # Analyze
    ana = sub.add_parser("analyze", help="Analyze recorded sessions")
    ana.add_argument("--data-file", type=str, default="fishing_flow_data.json", help="Data file path")

    # Sample
    samp = sub.add_parser("sample", help="Load sample data and analyze")
    samp.add_argument("--data-file", type=str, default="fishing_flow_data.json", help="Data file path")

    # Report
    rep = sub.add_parser("report", help="Generate a text report")
    rep.add_argument("--data-file", type=str, default="fishing_flow_data.json", help="Data file path")

    args = parser.parse_args()

    if args.command == "record":
        # Parse species
        species = {}
        if args.species:
            for pair in args.species.split(","):
                if ":" in pair:
                    name, count = pair.split(":", 1)
                    species[name.strip()] = int(count.strip())

        session = FishingSession(
            flow_state=args.flow,
            friction_mask=args.friction,
            catch_count=args.catch,
            species=species,
            location=args.location,
            duration_min=args.duration,
            crew_size=args.crew,
            timestamp=datetime.now().isoformat(),
            notes=args.notes,
        )

        # Load existing, append, save
        corr = FishingFlowCorrelator()
        data_path = Path(args.data_file)
        if data_path.exists():
            corr.load(data_path)
        corr.record(session)
        corr.save(data_path)
        print(f"Recorded session: {session.catch_count} fish, Φ={session.flow_state:.2f}")

    elif args.command == "analyze":
        corr = FishingFlowCorrelator()
        data_path = Path(args.data_file)
        if not data_path.exists():
            print(f"No data file: {data_path}")
            sys.exit(1)
        corr.load(data_path)
        results = corr.correlate()
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif args.command == "sample":
        corr = FishingFlowCorrelator()
        for s in SAMPLE_SESSIONS:
            corr.record(s)
        print(corr.report())

    elif args.command == "report":
        corr = FishingFlowCorrelator()
        data_path = Path(args.data_file)
        if not data_path.exists():
            print(f"No data file: {data_path}")
            sys.exit(1)
        corr.load(data_path)
        print(corr.report())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
