"""Tests for the AELMA benchmark suite (tests/benchmarks.py).

These verify the suite's correctness: each benchmark produces a sane
BenchmarkResult, baselines are defined for every benchmark, and the
JSON / text report generators emit well-formed output. Workloads are
run at a small scale to keep the test suite fast.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# tests/benchmarks.py is a runnable script, not a test module, so load it
# explicitly by path (its name also avoids pytest collecting it as tests).
_SPEC = importlib.util.spec_from_file_location(
    "aelma_benchmarks", Path(__file__).with_name("benchmarks.py")
)
benchmarks = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("aelma_benchmarks", benchmarks)
_SPEC.loader.exec_module(benchmarks)


@pytest.fixture(scope="module")
def suite_results(tmp_path_factory):
    """Run the full suite once at a small scale and share the results."""
    workdir = tmp_path_factory.mktemp("bench_suite")
    return benchmarks.run_suite(scale=0.05, repeats=1, workdir=workdir)


class TestBenchmarkSuite:
    def test_all_benchmarks_run(self, suite_results):
        names = {r.name for r in suite_results}
        assert names == set(benchmarks.BASELINES), (
            "every benchmark must have a baseline and vice versa"
        )
        assert len(suite_results) == 4

    def test_results_are_well_formed(self, suite_results):
        for r in suite_results:
            assert r.iterations > 0
            assert r.repeats >= 1
            assert r.ops_per_sec > 0.0
            assert r.best_ops_per_sec >= r.ops_per_sec
            assert r.avg_ms_per_op > 0.0
            assert r.baseline_ops_per_sec == benchmarks.BASELINES[r.name]
            assert isinstance(r.passed, bool)

    def test_baselines_met_at_small_scale(self, suite_results):
        # Baselines are conservative (e.g. 1000 ops/sec) and should hold
        # even for small workloads on modest hardware.
        failed = [r.name for r in suite_results if not r.passed]
        assert not failed, f"benchmarks below baseline: {failed}"

    def test_results_serializable(self, suite_results):
        for r in suite_results:
            round_tripped = json.loads(json.dumps(r.to_dict()))
            assert round_tripped["name"] == r.name
            assert round_tripped["ops_per_sec"] == pytest.approx(r.ops_per_sec)


class TestIndividualBenchmarks:
    def test_nmea_parsing(self):
        result = benchmarks.bench_nmea_parsing(iterations=200, repeats=1)
        assert result.name == "nmea_parsing"
        assert result.iterations == 200
        assert result.ops_per_sec > 0.0

    def test_watcher_evaluation(self):
        result = benchmarks.bench_watcher_evaluation(iterations=200, repeats=1)
        assert result.name == "watcher_evaluation"
        assert result.details["rules_registered"] >= 1
        assert result.ops_per_sec > 0.0

    def test_telemetry_filter(self, tmp_path):
        result = benchmarks.bench_telemetry_filter(
            n_records=200, repeats=1, workdir=tmp_path)
        assert result.name == "telemetry_filter"
        assert result.iterations == 400  # 2 scans x 200 records
        assert result.ops_per_sec > 0.0

    def test_a2a_aggregations(self, tmp_path):
        result = benchmarks.bench_a2a_aggregations(
            n_records=100, repeats=1, workdir=tmp_path)
        assert result.name == "a2a_aggregations"
        assert result.iterations == 400  # 4 aggregations x 100 records
        assert result.ops_per_sec > 0.0


class TestBaselineComparison:
    def test_pass_when_above_baseline(self):
        result = benchmarks.BenchmarkResult(
            name="x", unit="ops", iterations=10, repeats=1,
            ops_per_sec=2000.0, best_ops_per_sec=2000.0,
            avg_ms_per_op=0.5, baseline_ops_per_sec=1000.0, passed=True)
        assert result.passed

    def test_fail_when_below_baseline(self):
        def slow_op():
            time.sleep(0.001)
            return 1

        result = benchmarks._measure(
            "slow", "ops", slow_op, repeats=1, baseline=1e12)
        assert not result.passed
        assert result.ops_per_sec < 1e12


class TestReportGeneration:
    def test_json_report_structure(self, suite_results):
        report = benchmarks.build_json_report(suite_results)
        assert report["suite"] == "aelma-benchmarks"
        assert report["summary"]["total"] == len(suite_results)
        assert report["summary"]["passed"] + report["summary"]["failed"] == \
            report["summary"]["total"]
        assert len(report["benchmarks"]) == len(suite_results)
        for entry in report["benchmarks"]:
            assert {"name", "ops_per_sec", "baseline_ops_per_sec",
                    "passed"} <= set(entry)

    def test_json_report_written_to_disk(self, suite_results, tmp_path):
        out = tmp_path / "reports" / "bench.json"
        report = benchmarks.write_json_report(suite_results, out)
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded == report

    def test_text_report_contents(self, suite_results):
        text = benchmarks.format_text_report(suite_results)
        assert "AELMA Performance Benchmark Report" in text
        for r in suite_results:
            assert r.name in text
            assert ("PASS" if r.passed else "FAIL") in text
        assert f"{len(suite_results)}" in text  # summary counts

    def test_text_report_marks_failures(self):
        failing = benchmarks.BenchmarkResult(
            name="too_slow", unit="ops", iterations=1, repeats=1,
            ops_per_sec=1.0, best_ops_per_sec=1.0, avg_ms_per_op=1000.0,
            baseline_ops_per_sec=1000.0, passed=False)
        text = benchmarks.format_text_report([failing])
        assert "FAIL" in text
        assert "0/1 benchmarks met their baseline" in text
