"""Tests for the AELMA health check system (twin/health.py).

Coverage:

  1. Websocket component: ok when connected, degraded when disconnected,
     fail when the bridge breaker is OPEN.
  2. Log files component: ok on writable paths, fail on a closed A2A log
     or an unwritable target.
  3. Memory component: ok under the limit, degraded over it, ok when the
     RSS probe is unavailable.
  4. Report aggregation: health/ready/live status mapping and codes.
  5. HTTP integration: real requests against a live server on an
     ephemeral port (status lines, JSON bodies, 404/405 handling).
  6. TwinCore wiring: health_port construction and bridge_connected flag.

Run from the repo root:  python -m pytest tests/health.test.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.circuit_breaker import State  # noqa: E402
from twin.core import TwinCore  # noqa: E402
from twin.health import HealthChecker  # noqa: E402


def make_core(tmp_path: Path, **kwargs) -> TwinCore:
    """A TwinCore whose file paths all live under the pytest tmp dir."""
    kwargs.setdefault("bathymetry_path", tmp_path / "bathymetry.json")
    kwargs.setdefault("a2a_log_path", tmp_path / "a2a.jsonl")
    return TwinCore(**kwargs)


def make_checker(tmp_path: Path, **kwargs) -> HealthChecker:
    core_kwargs = kwargs.pop("core_kwargs", {})
    return HealthChecker(make_core(tmp_path, **core_kwargs), **kwargs)


async def trip_breaker(core: TwinCore) -> None:
    """Drive the bridge breaker OPEN through the public record path."""
    for _ in range(core.bridge_breaker.failure_threshold):
        await core.bridge_breaker.acquire()
        await core.bridge_breaker.record_failure()


async def http_get(port: int, path: str, method: str = "GET") -> tuple[int, dict]:
    """Minimal async HTTP client returning (status code, parsed JSON body)."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(f"{method} {path} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
        await writer.drain()
        status_line = await reader.readline()
        code = int(status_line.split()[1])
        while True:  # drain headers
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
        body = await reader.read()
        return code, json.loads(body)
    finally:
        writer.close()


# --------------------------------------------------------------------- #
# 1. Websocket component
# --------------------------------------------------------------------- #
class TestWebsocketCheck:
    def test_degraded_when_not_connected(self, tmp_path):
        hc = make_checker(tmp_path)
        result = hc.check_websocket()
        assert result["status"] == "degraded"
        assert result["connected"] is False
        assert result["breaker"]["state"] == "closed"

    def test_ok_when_connected(self, tmp_path):
        hc = make_checker(tmp_path)
        hc.core.bridge_connected = True
        result = hc.check_websocket()
        assert result["status"] == "ok"
        assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_fail_when_breaker_open(self, tmp_path):
        hc = make_checker(tmp_path)
        await trip_breaker(hc.core)
        assert hc.core.bridge_breaker.state is State.OPEN
        result = hc.check_websocket()
        assert result["status"] == "fail"
        assert result["breaker"]["state"] == "open"

    @pytest.mark.asyncio
    async def test_connected_but_breaker_open_still_fails(self, tmp_path):
        hc = make_checker(tmp_path)
        await trip_breaker(hc.core)
        hc.core.bridge_connected = True
        assert hc.check_websocket()["status"] == "fail"


# --------------------------------------------------------------------- #
# 2. Log files component
# --------------------------------------------------------------------- #
class TestLogFilesCheck:
    def test_ok_on_writable_paths(self, tmp_path):
        hc = make_checker(tmp_path)
        result = hc.check_log_files()
        assert result["status"] == "ok"
        assert result["a2a_log"]["status"] == "ok"
        assert result["bathymetry"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_fail_when_a2a_log_closed(self, tmp_path):
        hc = make_checker(tmp_path)
        await hc.core.a2a_log.close()
        result = hc.check_log_files()
        assert result["status"] == "fail"
        assert result["a2a_log"]["status"] == "fail"

    def test_fail_when_target_is_a_directory(self, tmp_path):
        # Bathymetry path points at an existing directory: cannot persist.
        hc = make_checker(
            tmp_path, core_kwargs={"bathymetry_path": tmp_path / "bathy_dir"}
        )
        hc.core.bathymetry_path.mkdir()
        result = hc.check_log_files()
        assert result["status"] == "fail"
        assert result["bathymetry"]["status"] == "fail"
        assert "is a directory" in result["bathymetry"]["error"]


# --------------------------------------------------------------------- #
# 3. Memory component
# --------------------------------------------------------------------- #
class TestMemoryCheck:
    def test_ok_under_limit(self, tmp_path):
        hc = make_checker(tmp_path, memory_limit_mb=512.0,
                          rss_probe=lambda: 100 * 1024 * 1024)
        result = hc.check_memory()
        assert result["status"] == "ok"
        assert result["rss_mb"] == 100.0

    def test_degraded_over_limit(self, tmp_path):
        hc = make_checker(tmp_path, memory_limit_mb=512.0,
                          rss_probe=lambda: 600 * 1024 * 1024)
        result = hc.check_memory()
        assert result["status"] == "degraded"
        assert result["rss_mb"] == 600.0

    def test_ok_when_probe_unavailable(self, tmp_path):
        hc = make_checker(tmp_path, rss_probe=lambda: None)
        result = hc.check_memory()
        assert result["status"] == "ok"
        assert result["rss_mb"] is None

    def test_default_probe_returns_int_or_none(self, tmp_path):
        hc = make_checker(tmp_path)
        result = hc.check_memory()
        assert result["status"] == "ok"
        assert result["rss_mb"] is None or result["rss_mb"] > 0


# --------------------------------------------------------------------- #
# 4. Report aggregation
# --------------------------------------------------------------------- #
class TestReports:
    def test_health_degraded_on_fresh_core(self, tmp_path):
        hc = make_checker(tmp_path)
        code, body = hc.health_report()
        assert code == 200
        assert body["status"] == "degraded"
        assert set(body["components"]) == {"websocket", "log_files", "memory"}

    @pytest.mark.asyncio
    async def test_health_unhealthy_when_component_fails(self, tmp_path):
        hc = make_checker(tmp_path)
        await trip_breaker(hc.core)
        code, body = hc.health_report()
        assert code == 503
        assert body["status"] == "unhealthy"

    def test_health_healthy_when_connected(self, tmp_path):
        hc = make_checker(tmp_path)
        hc.core.bridge_connected = True
        code, body = hc.health_report()
        assert code == 200
        assert body["status"] == "healthy"

    def test_ready_requires_bridge_connection(self, tmp_path):
        hc = make_checker(tmp_path)
        code, body = hc.ready_report()
        assert code == 503
        assert body["status"] == "not_ready"
        hc.core.bridge_connected = True
        code, body = hc.ready_report()
        assert code == 200
        assert body["status"] == "ready"

    @pytest.mark.asyncio
    async def test_ready_503_on_component_failure(self, tmp_path):
        hc = make_checker(tmp_path)
        hc.core.bridge_connected = True
        await trip_breaker(hc.core)
        code, body = hc.ready_report()
        assert code == 503
        assert body["status"] == "not_ready"

    def test_live_always_200(self, tmp_path):
        hc = make_checker(tmp_path)
        code, body = hc.live_report()
        assert code == 200
        assert body["status"] == "alive"
        assert body["uptime_s"] >= 0


# --------------------------------------------------------------------- #
# 5. HTTP integration
# --------------------------------------------------------------------- #
class TestHTTPServer:
    @pytest.mark.asyncio
    async def test_live_endpoint_over_http(self, tmp_path):
        hc = make_checker(tmp_path, host="127.0.0.1", port=0)
        await hc.start()
        try:
            assert hc.port != 0
            code, body = await http_get(hc.port, "/live")
            assert code == 200
            assert body["status"] == "alive"
        finally:
            await hc.stop()

    @pytest.mark.asyncio
    async def test_health_and_ready_over_http(self, tmp_path):
        hc = make_checker(tmp_path, host="127.0.0.1", port=0)
        await hc.start()
        try:
            code, body = await http_get(hc.port, "/health")
            assert code == 200
            assert body["status"] == "degraded"
            assert body["components"]["websocket"]["connected"] is False

            code, body = await http_get(hc.port, "/ready")
            assert code == 503
            assert body["status"] == "not_ready"

            hc.core.bridge_connected = True
            code, body = await http_get(hc.port, "/ready")
            assert code == 200
            assert body["status"] == "ready"

            code, body = await http_get(hc.port, "/health")
            assert code == 200
            assert body["status"] == "healthy"
        finally:
            await hc.stop()

    @pytest.mark.asyncio
    async def test_unknown_path_returns_404(self, tmp_path):
        hc = make_checker(tmp_path, host="127.0.0.1", port=0)
        await hc.start()
        try:
            code, body = await http_get(hc.port, "/nope")
            assert code == 404
            assert body["status"] == "not_found"
        finally:
            await hc.stop()

    @pytest.mark.asyncio
    async def test_non_get_returns_405(self, tmp_path):
        hc = make_checker(tmp_path, host="127.0.0.1", port=0)
        await hc.start()
        try:
            code, body = await http_get(hc.port, "/live", method="POST")
            assert code == 405
            assert body["status"] == "method_not_allowed"
        finally:
            await hc.stop()

    @pytest.mark.asyncio
    async def test_query_string_is_ignored(self, tmp_path):
        hc = make_checker(tmp_path, host="127.0.0.1", port=0)
        await hc.start()
        try:
            code, _ = await http_get(hc.port, "/live?verbose=1")
            assert code == 200
        finally:
            await hc.stop()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, tmp_path):
        hc = make_checker(tmp_path, host="127.0.0.1", port=0)
        await hc.start()
        port = hc.port
        await hc.start()
        assert hc.port == port
        await hc.stop()


# --------------------------------------------------------------------- #
# 6. TwinCore wiring
# --------------------------------------------------------------------- #
class TestTwinCoreWiring:
    def test_health_checker_created_by_default(self, tmp_path):
        core = make_core(tmp_path)
        assert isinstance(core.health, HealthChecker)
        assert core.health.port == 8091
        assert core.health.core is core

    def test_health_disabled_with_none(self, tmp_path):
        core = make_core(tmp_path, health_port=None)
        assert core.health is None

    def test_custom_health_port(self, tmp_path):
        core = make_core(tmp_path, health_port=9999)
        assert core.health.port == 9999

    def test_bridge_connected_defaults_false(self, tmp_path):
        core = make_core(tmp_path)
        assert core.bridge_connected is False
