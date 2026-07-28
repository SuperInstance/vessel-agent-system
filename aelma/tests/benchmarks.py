"""AELMA performance benchmark suite.

Measures throughput of the four hot paths in the system:

1. NMEA parsing          -- bridge.nmea.parse_sentence (sentences/sec)
2. Watcher evaluation    -- twin.watchers.WatcherRegistry.evaluate (evals/sec)
3. TelemetryQuery filter -- build_kimi.twin.telemetry_query (records scanned/sec)
4. A2AQuery aggregations -- twin.a2a_query (records processed/sec)

Each result is compared against a baseline throughput (see ``BASELINES``)
so regressions are visible at a glance. Reports can be emitted as JSON
(machine-readable, for CI/archival) and as a human-readable text table.

Timing uses ``time.perf_counter`` throughout.

Usage:
    python tests/benchmarks.py                      # run suite, print report
    python tests/benchmarks.py --json report.json   # also write JSON report
    python tests/benchmarks.py --scale 0.5 --repeats 5
    python tests/benchmarks.py --fail-on-regression # exit 1 if below baseline
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge import nmea
from build_kimi.twin.telemetry_query import TelemetryQuery
from twin.a2a_log import A2ALog
from twin.a2a_query import A2AQuery
from twin.watchers import WatcherRegistry

# ---------------------------------------------------------------------------
# Baselines: minimum acceptable throughput in ops/sec for each benchmark.
# The meaning of one "op" is documented per benchmark below.
# ---------------------------------------------------------------------------
BASELINES: dict[str, float] = {
    "nmea_parsing": 1_000.0,        # sentences parsed per second
    "watcher_evaluation": 1_000.0,  # frame evaluations per second
    "telemetry_filter": 1_000.0,    # log records scanned per second
    "a2a_aggregations": 1_000.0,    # log records processed per second
}

# Default workload sizes (scaled by --scale).
DEFAULT_NMEA_ITERATIONS = 4_000
DEFAULT_WATCHER_ITERATIONS = 4_000
DEFAULT_TELEMETRY_RECORDS = 5_000
DEFAULT_A2A_RECORDS = 2_000
DEFAULT_REPEATS = 3


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------
@dataclass
class BenchmarkResult:
    """Outcome of a single benchmark."""

    name: str
    unit: str                      # what one "op" is, e.g. "sentences"
    iterations: int                # ops performed per timed run
    repeats: int                   # number of timed runs
    ops_per_sec: float             # median throughput across repeats
    best_ops_per_sec: float        # best throughput across repeats
    avg_ms_per_op: float           # derived from ops_per_sec
    baseline_ops_per_sec: float    # minimum acceptable throughput
    passed: bool                   # ops_per_sec >= baseline
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Timing helper
# ---------------------------------------------------------------------------
def _measure(
    name: str,
    unit: str,
    op_count_fn: Callable[[], int],
    *,
    repeats: int,
    baseline: float,
    details: dict[str, Any] | None = None,
) -> BenchmarkResult:
    """Time ``op_count_fn`` (which returns the ops it performed) ``repeats``
    times and return the median/best throughput. One untimed warmup run
    is executed first so caches and imports don't skew the measurement."""
    op_count_fn()  # warmup
    rates: list[float] = []
    iterations = 0
    for _ in range(repeats):
        start = time.perf_counter()
        iterations = op_count_fn()
        elapsed = time.perf_counter() - start
        if elapsed <= 0:  # guard against clock resolution on tiny workloads
            elapsed = 1e-9
        rates.append(iterations / elapsed)
    median_rate = statistics.median(rates)
    return BenchmarkResult(
        name=name,
        unit=unit,
        iterations=iterations,
        repeats=repeats,
        ops_per_sec=median_rate,
        best_ops_per_sec=max(rates),
        avg_ms_per_op=1000.0 / median_rate if median_rate > 0 else 0.0,
        baseline_ops_per_sec=baseline,
        passed=median_rate >= baseline,
        details=details or {},
    )


# ---------------------------------------------------------------------------
# Workload data builders
# ---------------------------------------------------------------------------
def _make_nmea_sentence(body: str) -> str:
    """Wrap an NMEA body with '$' and a valid XOR checksum."""
    checksum = 0
    for ch in body:
        checksum ^= ord(ch)
    return f"${body}*{checksum:02X}"


def _sample_sentences() -> list[str]:
    """A representative mix of the sentence types the bridge parses."""
    bodies = [
        "GPGGA,123456,5648.080,N,13518.167,W,1,08,0.8,12.5,M,0.0,M,,",
        "GPRMC,123456,A,5648.080,N,13518.167,W,5.2,180.0,010125,,,",
        "SDDPT,73.2,-1.5,",
        "SDDBT,74.7,f,22.8,M,12.4,F",
        "WIMWV,45.0,T,10.5,K,A",
        "YXMTW,12.8,C",
    ]
    return [_make_nmea_sentence(b) for b in bodies]


def _build_watcher_registry() -> WatcherRegistry:
    """A registry with a realistic spread of rules over vessel state."""
    registry = WatcherRegistry(verbose=False)
    registry.add({
        "id": "shallow-water",
        "name": "Shallow water warning",
        "when": lambda f: 0 < f.get("depth_m", 999.0) < 2.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {"severity": "warning", "code": "SHALLOW_WATER"},
            "reason": lambda f: f"depth={f.get('depth_m', 0):.2f}m",
            "priority": lambda f: 0.85,
        },
    })
    registry.add({
        "id": "high-speed",
        "name": "Excessive speed",
        "when": lambda f: f.get("sog_kn", 0.0) > 12.0,
        "action": {"name": "raise_alert",
                   "payload": lambda f: {"severity": "info", "code": "HIGH_SPEED"}},
    })
    registry.add({
        "id": "heavy-wind",
        "name": "Heavy wind",
        "when": lambda f: f.get("wind_kts_true", 0.0) > 25.0,
        "action": {"name": "announce",
                   "payload": lambda f: f"Wind {f.get('wind_kts_true', 0):.0f} kn"},
    })
    registry.add({
        "id": "cold-water",
        "name": "Cold water",
        "when": lambda f: f.get("sea_temp_c", 99.0) < 4.0,
        "action": {"name": "set_panel_focus",
                   "payload": lambda f: {"panel": "environment"}},
    })
    registry.add({
        "id": "off-course",
        "name": "Off course",
        "when": lambda f: abs(f.get("cross_track_m", 0.0)) > 50.0,
        "action": {"name": "highlight_waypoint",
                   "payload": lambda f: {"waypoint": "next"}},
    })
    registry.add({
        "id": "low-baro",
        "name": "Falling barometer",
        "when": lambda f: 0 < f.get("baro_mb", 9999.0) < 990.0,
        "action": {"name": "raise_alert",
                   "payload": lambda f: {"severity": "warning", "code": "LOW_BARO"}},
    })
    return registry


def _sample_frame(i: int) -> dict[str, float]:
    """A vessel-state frame; values drift with ``i`` so rules fire unevenly."""
    return {
        "lat": 57.0531 + i * 1e-6,
        "lon": -135.33,
        "depth_m": 1.0 + (i % 50) * 0.5,
        "sog_kn": 4.0 + (i % 20) * 0.5,
        "cog_deg": 214.5,
        "wind_kts_true": 8.0 + (i % 30),
        "sea_temp_c": 9.5,
        "baro_mb": 1013.0 - (i % 40) * 0.5,
        "cross_track_m": float((i % 120) - 60),
    }


def _write_telemetry_log(path: Path, n_records: int) -> None:
    """Write a synthetic telemetry JSONL log across several channels."""
    channels = ["depth_m", "sog_kn", "wind_kts_true", "sea_temp_c"]
    qualities = ["good", "good", "good", "fair", "poor"]
    base_ns = 1_753_478_400_000_000_000
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n_records):
            packet = {
                "timestamp_ns": base_ns + i * 1_000_000_000,
                "source": "nmea0183",
                "channel": channels[i % len(channels)],
                "value": float((i * 7) % 100) + 0.5,
                "quality": qualities[i % len(qualities)],
            }
            f.write(json.dumps(packet) + "\n")


async def _write_a2a_log(path: Path, n_records: int) -> None:
    """Write a synthetic A2A action log via the real A2ALog writer."""
    log = A2ALog(path)
    sources = ["watcher", "llm", "system"]
    base_ts = 1_753_478_400.0
    for i in range(n_records):
        await log.append(
            f"action_{i % 6}",
            {"index": i, "severity": "warning" if i % 5 == 0 else "info"},
            source=sources[i % len(sources)],
            priority=0.1 + (i % 10) * 0.08,
            reason=f"benchmark record {i}",
            ts=base_ts + i * 5.0,
        )


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------
def bench_nmea_parsing(iterations: int, repeats: int) -> BenchmarkResult:
    """Throughput of bridge.nmea.parse_sentence over a mixed sentence set.

    One op = one sentence fully parsed (checksum verify + dispatch + readings).
    """
    sentences = _sample_sentences()

    def run() -> int:
        for i in range(iterations):
            nmea.parse_sentence(sentences[i % len(sentences)])
        return iterations

    return _measure(
        "nmea_parsing", "sentences", run,
        repeats=repeats, baseline=BASELINES["nmea_parsing"],
        details={"sentence_types": len(sentences)},
    )


def bench_watcher_evaluation(iterations: int, repeats: int) -> BenchmarkResult:
    """Throughput of WatcherRegistry.evaluate with a realistic rule set.

    One op = one full evaluation of all registered rules against one frame.
    """
    registry = _build_watcher_registry()
    n_rules = len(registry.rules) if hasattr(registry, "rules") else 6

    def run() -> int:
        for i in range(iterations):
            registry.evaluate(_sample_frame(i))
        return iterations

    return _measure(
        "watcher_evaluation", "evaluations", run,
        repeats=repeats, baseline=BASELINES["watcher_evaluation"],
        details={"rules_registered": n_rules},
    )


def bench_telemetry_filter(n_records: int, repeats: int,
                           workdir: Path) -> BenchmarkResult:
    """Throughput of TelemetryQuery filtering over a JSONL telemetry log.

    One op = one log record scanned (the generator streams the whole file,
    applying channel + value-range + quality predicates). A stats pass is
    included so aggregation cost is measured alongside raw filtering.
    """
    log_path = workdir / "telemetry_bench.jsonl"
    _write_telemetry_log(log_path, n_records)
    query = TelemetryQuery(log_path)

    def run() -> int:
        # Filtered scan: channel + value range + quality.
        matched = 0
        for _rec in query.filter(channel="depth_m",
                                 value_range=(10.0, 60.0),
                                 quality="good"):
            matched += 1
        # Aggregation pass over the same channel.
        stats = query.stats("value").filter(channel="depth_m")
        _ = (stats.mean, stats.stddev, stats.count, matched)
        return 2 * n_records  # two full-file scans per run

    return _measure(
        "telemetry_filter", "records", run,
        repeats=repeats, baseline=BASELINES["telemetry_filter"],
        details={"log_records": n_records, "scans_per_run": 2},
    )


def bench_a2a_aggregations(n_records: int, repeats: int,
                           workdir: Path) -> BenchmarkResult:
    """Throughput of A2AQuery aggregation methods over an A2A action log.

    One op = one log record processed. Each run performs four full-log
    aggregations: count_by, top_by, summary, and bucket_by_time.
    """
    log_path = workdir / "a2a_bench.jsonl"
    asyncio.run(_write_a2a_log(log_path, n_records))
    query = A2AQuery(log_path)

    async def aggregate_once() -> None:
        await query.count_by("source")
        await query.top_by("action", n=5)
        await query.summary()
        await query.bucket_by_time(300.0)

    def run() -> int:
        asyncio.run(aggregate_once())
        return 4 * n_records  # four full-log passes per run

    return _measure(
        "a2a_aggregations", "records", run,
        repeats=repeats, baseline=BASELINES["a2a_aggregations"],
        details={"log_records": n_records, "aggregations_per_run": 4},
    )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------
def run_suite(scale: float = 1.0, repeats: int = DEFAULT_REPEATS,
              workdir: Path | None = None) -> list[BenchmarkResult]:
    """Run all benchmarks and return their results in a stable order.

    ``scale`` multiplies the default workload sizes (use < 1 for smoke runs).
    Synthetic log files are written under ``workdir`` (a temporary directory
    is created when not given).
    """
    nmea_iters = max(10, int(DEFAULT_NMEA_ITERATIONS * scale))
    watcher_iters = max(10, int(DEFAULT_WATCHER_ITERATIONS * scale))
    telemetry_records = max(50, int(DEFAULT_TELEMETRY_RECORDS * scale))
    a2a_records = max(50, int(DEFAULT_A2A_RECORDS * scale))

    def _run(wd: Path) -> list[BenchmarkResult]:
        return [
            bench_nmea_parsing(nmea_iters, repeats),
            bench_watcher_evaluation(watcher_iters, repeats),
            bench_telemetry_filter(telemetry_records, repeats, wd),
            bench_a2a_aggregations(a2a_records, repeats, wd),
        ]

    if workdir is not None:
        return _run(Path(workdir))
    with tempfile.TemporaryDirectory(prefix="aelma_bench_") as tmp:
        return _run(Path(tmp))


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def build_json_report(results: list[BenchmarkResult]) -> dict[str, Any]:
    """Build the machine-readable report structure."""
    passed = sum(1 for r in results if r.passed)
    return {
        "suite": "aelma-benchmarks",
        "generated_at_unix": time.time(),
        "python_version": sys.version.split()[0],
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "all_passed": passed == len(results),
        },
        "benchmarks": [r.to_dict() for r in results],
    }


def write_json_report(results: list[BenchmarkResult], path: Path) -> dict[str, Any]:
    """Build the JSON report and write it to ``path``."""
    report = build_json_report(results)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def format_text_report(results: list[BenchmarkResult]) -> str:
    """Render the human-readable report as a text table."""
    name_w = max(len(r.name) for r in results + [BenchmarkResult(
        "benchmark", "", 0, 0, 0, 0, 0, 0, True)])
    lines = [
        "AELMA Performance Benchmark Report",
        "=" * 72,
        f"{'benchmark':<{name_w}}  {'throughput':>14}  {'baseline':>12}  "
        f"{'avg ms/op':>10}  status",
        "-" * 72,
    ]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(
            f"{r.name:<{name_w}}  "
            f"{r.ops_per_sec:>10,.0f} {r.unit[:3]}/s  "
            f"{r.baseline_ops_per_sec:>9,.0f}/s  "
            f"{r.avg_ms_per_op:>10.4f}  {status}"
        )
    lines.append("-" * 72)
    passed = sum(1 for r in results if r.passed)
    lines.append(
        f"{passed}/{len(results)} benchmarks met their baseline "
        f"(throughput = median of timed repeats, time.perf_counter)"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AELMA performance benchmark suite")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="workload size multiplier (default 1.0)")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS,
                        help="timed repeats per benchmark (default %(default)s)")
    parser.add_argument("--json", type=Path, default=None,
                        help="also write the JSON report to this path")
    parser.add_argument("--fail-on-regression", action="store_true",
                        help="exit 1 if any benchmark is below its baseline")
    args = parser.parse_args(argv)

    results = run_suite(scale=args.scale, repeats=args.repeats)
    print(format_text_report(results))
    if args.json is not None:
        write_json_report(results, args.json)
        print(f"\nJSON report written to {args.json}")
    if args.fail_on_regression and not all(r.passed for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
