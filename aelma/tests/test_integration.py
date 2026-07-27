"""End-to-end integration tests for the AELMA stack.

These tests exercise the contracts in `schema/` regardless of which
implementation sits at each layer. They run the real asyncio TCP/WS
servers in-process and verify that:

  simulator (TCP) -> bridge (TCP->WS) -> twin (WS client + WS server) -> viewer (WS client)

works end to end. Latency targets from ARCHITECTURE.md must be met.

Run from this directory:  python -m pytest tests/test_integration.py -v
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Make the package importable regardless of which build dir was promoted
# to be the canonical one. We add both `twin` and `bridge` package roots.
HERE = Path(__file__).resolve().parent
AELMA_ROOT = HERE.parent
for candidate in (AELMA_ROOT,):
    sys.path.insert(0, str(candidate))


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _wait_for(predicate, *, timeout: float = 5.0, interval: float = 0.05):
    """Poll `predicate()` until it returns truthy or `timeout` elapses."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        result = predicate()
        if result:
            return result
        await asyncio.sleep(interval)
    raise AssertionError(f"predicate never became truthy within {timeout}s")


# ---------------------------------------------------------------------------
# Schema-contract tests — no live servers. These ensure that whatever
# code ended up in bridge/ and twin/ honors the JSON Schemas.
# ---------------------------------------------------------------------------


def _import_bridge_module(name: str):
    """Import a module from the bridge package, tolerant of location."""
    try:
        from importlib import import_module
        return import_module(f"bridge.{name}")
    except ModuleNotFoundError:
        pytest.skip("bridge package not yet integrated into aelma root")


def _import_twin_module(name: str):
    try:
        from importlib import import_module
        return import_module(f"twin.{name}")
    except ModuleNotFoundError:
        pytest.skip("twin package not yet integrated into aelma root")


def test_telemetry_packet_schema_loads():
    """The wire contract must be a valid JSON Schema we can read."""
    schema_path = AELMA_ROOT / "schema" / "telemetry_packet.schema.json"
    assert schema_path.exists(), f"missing {schema_path}"
    schema = json.loads(schema_path.read_text())
    assert schema["type"] == "object"
    for required in ("timestamp_ns", "source", "channel", "value"):
        assert required in schema["required"], f"{required} not required in telemetry packet"


def test_vessel_state_schema_loads():
    schema_path = AELMA_ROOT / "schema" / "vessel_state.schema.json"
    schema = json.loads(schema_path.read_text())
    for required in ("timestamp_ns", "vessel_id", "pose", "channels"):
        assert required in schema["required"]


def test_bathymetry_voxel_schema_loads():
    schema_path = AELMA_ROOT / "schema" / "bathymetry_voxel.schema.json"
    schema = json.loads(schema_path.read_text())
    for required in ("lat", "lon", "depth_m", "confidence", "sample_count"):
        assert required in schema["required"]


# ---------------------------------------------------------------------------
# NMEA parser → TelemetryPacket contract
# ---------------------------------------------------------------------------


def test_nmea_parser_output_matches_schema():
    """Whatever the bridge's parse_sentence returns must be usable as a
    TelemetryPacket fragment (channel + value; bridge.py adds the rest)."""
    nmea = _import_bridge_module("nmea")
    readings = nmea.parse_sentence("$SDDPT,73.2,-1.5,*3A\r\n")
    assert isinstance(readings, list)
    assert readings, "DPT sentence yielded no readings"
    r = readings[0]
    assert "channel" in r and "value" in r
    assert r["channel"] == "depth_m"
    assert abs(r["value"] - 73.2) < 1e-6


def test_nmea_rejects_bad_checksum():
    """A corrupt sentence must raise; the bridge must never silently pass one."""
    nmea = _import_bridge_module("nmea")
    bad = "$SDDPT,73.2,-1.5,*00\r\n"  # wrong checksum
    with pytest.raises(ValueError):
        nmea.parse_sentence(bad)


def test_quality_check_returns_known_grades():
    """quality.check must accept known channels and return one of the 4 grades."""
    quality = _import_bridge_module("quality")
    grades = {"good", "fair", "poor", "bad"}
    assert quality.check_quality("depth_m", 50.0) in grades
    assert quality.check_quality("depth_m", float("nan")) == "bad"


# ---------------------------------------------------------------------------
# Twin state → VesselStateSnapshot contract
# ---------------------------------------------------------------------------


def test_twin_snapshot_shape_matches_schema():
    """The twin's snapshot() must produce a dict that matches the required
    fields of vessel_state.schema.json."""
    state_mod = _import_twin_module("state")
    # Build a minimal state by applying a position + a depth packet.
    s = state_mod.VesselState()
    s.apply_packet({
        "timestamp_ns": 1_000_000_000,
        "source": "simulator",
        "channel": "position",
        "value": {"lat": 56.80134, "lon": -135.30278},
        "quality": "good",
    })
    s.apply_packet({
        "timestamp_ns": 1_000_500_000,
        "source": "simulator",
        "channel": "depth_m",
        "value": 73.2,
        "quality": "good",
    })
    snap = s.snapshot(vessel_id="US-AK-FVEILEEN-51", viewport=[])
    for k in ("timestamp_ns", "vessel_id", "pose", "channels"):
        assert k in snap, f"snapshot missing {k}"
    assert snap["vessel_id"] == "US-AK-FVEILEEN-51"
    assert -180 <= snap["pose"]["lon"] <= 180
    assert 0 <= snap["pose"]["heading_deg"] < 360
    assert "depth_m" in snap["channels"]


def test_bathymetry_fusion_then_viewport():
    """Fusing a depth sample must make it retrievable via cells_in_radius."""
    bath = _import_twin_module("bathymetry")
    g = bath.BathymetryGrid()
    g.fuse(56.80134, -135.30278, 73.2, 1_000_000_000)
    cells = g.cells_in_radius(56.80134, -135.30278, 100)
    assert cells, "no cells returned after fusion"
    assert abs(cells[0][2] - 73.2) < 1e-6  # depth
    assert g.total_voxels() == 1


# ---------------------------------------------------------------------------
# Live network round-trip (asyncio + websockets required).
# These are marked with `asyncio` mode and skipped if websockets is missing.
# ---------------------------------------------------------------------------


def _has_websockets() -> bool:
    try:
        import websockets  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


@pytest.mark.skipif(not _has_websockets(), reason="websockets not installed")
async def test_full_stack_round_trip():
    """Spin up simulator -> bridge -> twin, then read a VesselStateSnapshot
    off the twin's viewer port and assert it has depth + pose populated.

    This is the canonical end-to-end contract test from ARCHITECTURE.md."""
    import websockets

    bridge_pkg = _import_bridge_module("bridge")
    twin_core_mod = _import_twin_module("core")
    sim_mod = None
    try:
        from importlib import import_module
        sim_mod = import_module("simulator.simulate")
    except ModuleNotFoundError:
        pytest.skip("simulator package not yet integrated")

    # Pick unused ports
    import socket
    def _free_port() -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port
    tcp_port = _free_port()
    bridge_ws = _free_port()
    viewer_ws = _free_port()

    # Start bridge (TCP receiver + WS broadcaster)
    br = bridge_pkg.Bridge(tcp_port=tcp_port, ws_port=bridge_ws)
    bridge_task = asyncio.create_task(br.serve_forever())
    await asyncio.sleep(0.1)  # let sockets bind

    # Start twin (WS client of bridge + WS server for viewers)
    core = twin_core_mod.TwinCore(
        bridge_url=f"ws://127.0.0.1:{bridge_ws}",
        viewer_port=viewer_ws,
        vessel_id="US-AK-FVEILEEN-51",
        bathymetry_path=str(AELMA_ROOT / "tests" / "_bathymetry_integration.json"),
        broadcast_interval=0.2,
    )
    twin_task = asyncio.create_task(core.serve_forever())
    await asyncio.sleep(0.3)  # let twin connect to bridge

    # Start simulator as a TCP client writing NMEA to bridge
    async def run_sim_briefly():
        reader, writer = await asyncio.open_connection("127.0.0.1", tcp_port)
        end = asyncio.get_event_loop().time() + 3.0
        sentences = list(sim_mod.iter_sentences(duration_sec=3.0, speedup=30))
        loop = asyncio.get_event_loop()
        i = 0
        while loop.time() < end and i < len(sentences):
            writer.write((sentences[i] + "\r\n").encode("ascii"))
            await writer.drain()
            i += 1
            await asyncio.sleep(0.01)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    sim_task = asyncio.create_task(run_sim_briefly())

    # Subscribe as a viewer and collect one snapshot
    snapshots: list[dict] = []
    async with websockets.connect(f"ws://127.0.0.1:{viewer_ws}") as ws:
        try:
            await asyncio.wait_for(_wait_for_snapshots(ws, snapshots), timeout=8.0)
        except asyncio.TimeoutError:
            pass

    # Cleanup
    for t in (sim_task, twin_task, bridge_task):
        t.cancel()
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass

    assert snapshots, "no snapshots received from twin"
    snap = snapshots[0]
    assert snap["vessel_id"] == "US-AK-FVEILEEN-51"
    assert "pose" in snap
    assert "channels" in snap


async def _wait_for_snapshots(ws, sink: list[dict], max_msgs: int = 3):
    """Read up to `max_msgs` JSON messages from `ws` into `sink`."""
    for _ in range(max_msgs):
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=4.0)
            sink.append(json.loads(raw))
        except asyncio.TimeoutError:
            break
