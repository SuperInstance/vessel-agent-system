"""Tests for the AELMA circuit breaker (twin/circuit_breaker.py).

Mirrors the mini-agent's circuitBreaker.test.js suite, adapted to pytest
and asyncio. Coverage:

  1. Construction & defaults (CLOSED, validation of threshold/timeout).
  2. CLOSED-state failure counting and reset-on-success.
  3. Tripping OPEN at the failure threshold; acquire() blocks while OPEN.
  4. OPEN -> HALF_OPEN after the recovery timeout (fake clock).
  5. HALF_OPEN probe: success closes, failure re-opens and restarts timeout.
  6. Single-probe admission while HALF_OPEN.
  7. call() wrapper: result passthrough, failure recording, non-blocking
     CircuitBreakerOpen.
  8. reset() and stats().
  9. WebSocket integration: real localhost server through breaker.call(),
     and TwinCore wiring of bridge_breaker into the reconnect loop.

Run from the repo root:  python -m pytest tests/circuit_breaker.test.py -v
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.circuit_breaker import (  # noqa: E402
    CircuitBreaker,
    CircuitBreakerOpen,
    State,
)

try:
    import websockets

    _HAS_WEBSOCKETS = True
except ImportError:  # pragma: no cover - environment without websockets
    _HAS_WEBSOCKETS = False


class FakeClock:
    """Deterministic monotonic clock, advanced manually by tests."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def make_breaker(
    threshold: int = 3,
    timeout: float = 30.0,
    clock: FakeClock | None = None,
) -> CircuitBreaker:
    return CircuitBreaker(
        name="test",
        failure_threshold=threshold,
        recovery_timeout=timeout,
        clock=clock or FakeClock(),
    )


async def fail_n(breaker: CircuitBreaker, n: int) -> None:
    """Record n failures through the public acquire/record path."""
    for _ in range(n):
        await breaker.acquire()
        await breaker.record_failure()


# --------------------------------------------------------------------- #
# 1. Construction & defaults
# --------------------------------------------------------------------- #
class TestConstruction:
    def test_starts_closed_with_zero_failures(self):
        cb = CircuitBreaker(name="x")
        assert cb.state is State.CLOSED
        assert cb.failure_count == 0
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 30.0

    def test_configurable_threshold_and_timeout(self):
        cb = CircuitBreaker(name="x", failure_threshold=2, recovery_timeout=5.0)
        assert cb.failure_threshold == 2
        assert cb.recovery_timeout == 5.0

    @pytest.mark.parametrize("bad", [0, -1])
    def test_rejects_nonpositive_threshold(self, bad):
        with pytest.raises(ValueError):
            CircuitBreaker(failure_threshold=bad)

    @pytest.mark.parametrize("bad", [0.0, -1.0])
    def test_rejects_nonpositive_timeout(self, bad):
        with pytest.raises(ValueError):
            CircuitBreaker(recovery_timeout=bad)


# --------------------------------------------------------------------- #
# 2. CLOSED-state failure counting
# --------------------------------------------------------------------- #
class TestClosedState:
    @pytest.mark.asyncio
    async def test_failures_below_threshold_keep_closed(self):
        cb = make_breaker(threshold=3)
        await fail_n(cb, 2)
        assert cb.state is State.CLOSED
        assert cb.failure_count == 2

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        cb = make_breaker(threshold=3)
        await fail_n(cb, 2)
        await cb.acquire()
        await cb.record_success()
        assert cb.failure_count == 0
        # Two more failures still don't trip: the count restarted.
        await fail_n(cb, 2)
        assert cb.state is State.CLOSED


# --------------------------------------------------------------------- #
# 3. Tripping OPEN
# --------------------------------------------------------------------- #
class TestOpenState:
    @pytest.mark.asyncio
    async def test_trips_open_at_threshold(self):
        cb = make_breaker(threshold=3)
        await fail_n(cb, 3)
        assert cb.state is State.OPEN
        assert cb.failure_count == 3

    @pytest.mark.asyncio
    async def test_acquire_blocks_while_open(self):
        clock = FakeClock()
        cb = make_breaker(threshold=2, timeout=30.0, clock=clock)
        await fail_n(cb, 2)
        assert cb.state is State.OPEN
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(cb.acquire(), timeout=0.05)

    @pytest.mark.asyncio
    async def test_acquire_unblocks_when_timeout_elapses(self):
        clock = FakeClock()
        cb = make_breaker(threshold=1, timeout=30.0, clock=clock)
        await fail_n(cb, 1)

        async def advance_clock():
            await asyncio.sleep(0.02)
            clock.advance(31.0)

        advancer = asyncio.create_task(advance_clock())
        # No timeout error: acquire() wakes once the gate re-opens.
        await asyncio.wait_for(cb.acquire(), timeout=1.0)
        await advancer
        assert cb.state is State.HALF_OPEN


# --------------------------------------------------------------------- #
# 4-5. HALF_OPEN transitions
# --------------------------------------------------------------------- #
class TestHalfOpen:
    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self):
        clock = FakeClock()
        cb = make_breaker(threshold=1, timeout=10.0, clock=clock)
        await fail_n(cb, 1)
        assert cb.state is State.OPEN
        clock.advance(9.9)
        assert cb.state is State.OPEN
        clock.advance(0.2)
        assert cb.state is State.HALF_OPEN

    @pytest.mark.asyncio
    async def test_probe_success_closes_breaker(self):
        clock = FakeClock()
        cb = make_breaker(threshold=1, timeout=10.0, clock=clock)
        await fail_n(cb, 1)
        clock.advance(10.0)
        await cb.acquire()
        assert cb.state is State.HALF_OPEN
        await cb.record_success()
        assert cb.state is State.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_probe_failure_reopens_and_restarts_timeout(self):
        clock = FakeClock()
        cb = make_breaker(threshold=1, timeout=10.0, clock=clock)
        await fail_n(cb, 1)
        clock.advance(10.0)
        await cb.acquire()
        await cb.record_failure()
        assert cb.state is State.OPEN
        # Old elapsed time must not count against the new timeout.
        clock.advance(9.9)
        assert cb.state is State.OPEN
        clock.advance(0.1)
        assert cb.state is State.HALF_OPEN

    @pytest.mark.asyncio
    async def test_single_probe_admitted_while_half_open(self):
        clock = FakeClock()
        cb = make_breaker(threshold=1, timeout=10.0, clock=clock)
        await fail_n(cb, 1)
        clock.advance(10.0)
        await cb.acquire()  # the probe
        assert cb.state is State.HALF_OPEN
        # A second concurrent attempt must wait until the probe resolves.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(cb.acquire(), timeout=0.05)
        # Once the probe fails -> OPEN; after timeout another probe is let in.
        await cb.record_failure()
        clock.advance(10.0)
        await asyncio.wait_for(cb.acquire(), timeout=1.0)
        assert cb.state is State.HALF_OPEN


# --------------------------------------------------------------------- #
# 7. call() wrapper
# --------------------------------------------------------------------- #
class TestCall:
    @pytest.mark.asyncio
    async def test_call_returns_result_and_records_success(self):
        cb = make_breaker()

        async def good(x):
            return x * 2

        assert await cb.call(good, 21) == 42
        assert cb.state is State.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_records_failure_and_reraises(self):
        cb = make_breaker(threshold=2)

        async def bad():
            raise ConnectionError("refused")

        with pytest.raises(ConnectionError):
            await cb.call(bad)
        assert cb.failure_count == 1
        with pytest.raises(ConnectionError):
            await cb.call(bad)
        assert cb.state is State.OPEN

    @pytest.mark.asyncio
    async def test_call_nonblocking_raises_when_open(self):
        clock = FakeClock()
        cb = make_breaker(threshold=1, timeout=60.0, clock=clock)

        async def bad():
            raise ConnectionError("refused")

        async def good():
            return "ok"

        with pytest.raises(ConnectionError):
            await cb.call(bad)
        with pytest.raises(CircuitBreakerOpen):
            await cb.call(good, blocking=False)
        # After the timeout the non-blocking call probes and succeeds.
        clock.advance(60.0)
        assert await cb.call(good, blocking=False) == "ok"
        assert cb.state is State.CLOSED


# --------------------------------------------------------------------- #
# 8. reset() and stats()
# --------------------------------------------------------------------- #
class TestAdmin:
    @pytest.mark.asyncio
    async def test_reset_forces_closed(self):
        cb = make_breaker(threshold=1)
        await fail_n(cb, 1)
        assert cb.state is State.OPEN
        cb.reset()
        assert cb.state is State.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_stats_snapshot(self):
        cb = make_breaker(threshold=2, timeout=15.0)
        await fail_n(cb, 2)
        s = cb.stats()
        assert s == {
            "name": "test",
            "state": "open",
            "failure_count": 2,
            "failure_threshold": 2,
            "recovery_timeout": 15.0,
        }


# --------------------------------------------------------------------- #
# 9. WebSocket integration
# --------------------------------------------------------------------- #
@pytest.mark.skipif(not _HAS_WEBSOCKETS, reason="websockets not installed")
class TestWebSocketIntegration:
    @pytest.mark.asyncio
    async def test_connect_through_breaker_against_live_server(self):
        """A real WS handshake via breaker.call() closes a healthy circuit."""

        async def echo(ws):
            async for _ in ws:
                pass

        cb = make_breaker(threshold=2)
        async with websockets.serve(echo, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async def connect():
                return await websockets.connect(f"ws://127.0.0.1:{port}")

            ws = await cb.call(connect)
            await ws.close()
        assert cb.state is State.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_refused_connections_trip_breaker(self):
        """Connecting to a dead port through call() trips the breaker OPEN."""
        cb = make_breaker(threshold=3, timeout=60.0)

        async def connect():
            return await websockets.connect("ws://127.0.0.1:1")

        for _ in range(3):
            with pytest.raises(OSError):
                await cb.call(connect)
        assert cb.state is State.OPEN
        assert cb.failure_count == 3

    @pytest.mark.asyncio
    async def test_reconnect_loop_recovers_after_outage(self):
        """Fail-closed-then-recover: a stub connect that comes back to life."""
        clock = FakeClock()
        cb = make_breaker(threshold=2, timeout=30.0, clock=clock)
        attempts = 0

        async def flaky_connect():
            nonlocal attempts
            attempts += 1
            if attempts <= 2:
                raise OSError("connection refused")
            return "connected"

        # Two failures trip the breaker.
        for _ in range(2):
            with pytest.raises(OSError):
                await cb.call(flaky_connect)
        assert cb.state is State.OPEN

        # Simulate the twin's retry cadence: advance past the timeout,
        # then the next blocking call probes and succeeds.
        clock.advance(30.0)
        assert await cb.call(flaky_connect) == "connected"
        assert cb.state is State.CLOSED
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_twin_core_wires_bridge_breaker(self):
        from twin.core import TwinCore

        core = TwinCore(
            breaker_failure_threshold=7,
            breaker_recovery_timeout=12.5,
        )
        assert core.bridge_breaker.name == "bridge"
        assert core.bridge_breaker.failure_threshold == 7
        assert core.bridge_breaker.recovery_timeout == 12.5
        assert core.bridge_breaker.state is State.CLOSED

    @pytest.mark.asyncio
    async def test_twin_core_default_breaker(self):
        from twin.core import TwinCore

        core = TwinCore()
        assert core.bridge_breaker.failure_threshold == 5
        assert core.bridge_breaker.recovery_timeout == 30.0
