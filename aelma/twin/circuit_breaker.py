"""Asyncio circuit breaker for AELMA's external connections.

Protects the twin's WebSocket links (bridge client, upstream services)
from hammering a dead peer. Mirrors the mini-agent's ``circuitBreaker.js``
state machine:

- **CLOSED** — attempts flow through; failures are counted. Reaching
  ``failure_threshold`` consecutive failures trips the breaker OPEN.
- **OPEN** — attempts are blocked until ``recovery_timeout`` seconds have
  elapsed since the breaker tripped; then it probes via HALF_OPEN.
- **HALF_OPEN** — a single probe attempt is admitted. Success closes the
  breaker; failure trips it OPEN again and restarts the timeout.

State gating uses an :class:`asyncio.Event`: it is set while attempts are
permitted and cleared while the breaker is OPEN (or while a HALF_OPEN
probe is in flight), so blocked callers simply ``await`` it instead of
polling.

The breaker takes an injectable ``clock`` (defaults to
:func:`time.monotonic`) so tests can advance time deterministically.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

log = logging.getLogger("aelma.twin.circuit_breaker")

# Max time a parked acquire() waits before re-checking the clock. Keeps
# OPEN-state waits responsive to injected clocks and to gate transitions.
_PARK_INTERVAL = 0.1

T = TypeVar("T")


class State(enum.Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised by :meth:`CircuitBreaker.call` when ``blocking=False`` and the
    breaker is not admitting attempts."""


class CircuitBreaker:
    """Async circuit breaker with configurable failure threshold and timeout.

    Parameters
    ----------
    name:
        Label used in log messages.
    failure_threshold:
        Consecutive failures in CLOSED state that trip the breaker OPEN.
    recovery_timeout:
        Seconds the breaker stays OPEN before admitting a HALF_OPEN probe.
    clock:
        Monotonic time source, injectable for tests.
    """

    def __init__(
        self,
        name: str = "circuit",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be > 0")
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._clock = clock

        self._state = State.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._probe_active = False
        self._lock = asyncio.Lock()
        # Set while attempts are admitted; cleared while OPEN (or while a
        # HALF_OPEN probe is in flight) so waiters block on it.
        self._gate = asyncio.Event()
        self._gate.set()

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @property
    def state(self) -> State:
        """Current state, accounting for an elapsed recovery timeout."""
        self._refresh()
        return self._state

    @property
    def failure_count(self) -> int:
        """Consecutive failures counted since the last success/close."""
        return self._failures

    def stats(self) -> dict[str, Any]:
        """Snapshot of breaker state for logging / status surfaces."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failures,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }

    # ------------------------------------------------------------------ #
    # State machine
    # ------------------------------------------------------------------ #
    def _refresh(self) -> None:
        """OPEN -> HALF_OPEN once the recovery timeout has elapsed."""
        if (
            self._state is State.OPEN
            and self._clock() - self._opened_at >= self.recovery_timeout
        ):
            self._state = State.HALF_OPEN
            self._probe_active = False
            self._gate.set()
            log.info("breaker %s: OPEN -> HALF_OPEN (probing)", self.name)

    def _trip_open(self) -> None:
        self._state = State.OPEN
        self._opened_at = self._clock()
        self._probe_active = False
        self._gate.clear()
        log.warning(
            "breaker %s: tripped OPEN after %d failure(s); retry in %.0fs",
            self.name,
            self._failures,
            self.recovery_timeout,
        )

    def _close(self) -> None:
        self._state = State.CLOSED
        self._failures = 0
        self._probe_active = False
        self._gate.set()
        log.info("breaker %s: HALF_OPEN -> CLOSED (recovered)", self.name)

    # ------------------------------------------------------------------ #
    # Attempt admission
    # ------------------------------------------------------------------ #
    async def acquire(self) -> None:
        """Wait until the breaker admits an attempt, then take it.

        Returns immediately while CLOSED. While OPEN, blocks until the
        recovery timeout elapses; in HALF_OPEN exactly one probe is
        admitted at a time and further callers keep waiting.
        """
        while True:
            async with self._lock:
                self._refresh()
                if self._state is State.CLOSED:
                    return
                if self._state is State.HALF_OPEN and not self._probe_active:
                    self._probe_active = True
                    # Only one probe at a time: re-close the gate behind us.
                    self._gate.clear()
                    return
                if self._state is State.OPEN:
                    remaining = self.recovery_timeout - (self._clock() - self._opened_at)
                    wait = min(max(remaining, 0.0), _PARK_INTERVAL)
                else:
                    # HALF_OPEN with a probe in flight: wait for it to resolve.
                    wait = _PARK_INTERVAL
            try:
                # Bounded wait: re-checks the clock on wake so an injected
                # (e.g. fake) clock that jumps past the timeout is honored
                # even though nothing sets the gate.
                await asyncio.wait_for(self._gate.wait(), timeout=wait)
            except asyncio.TimeoutError:
                pass

    async def record_success(self) -> None:
        """Record a successful attempt: reset the count, close the breaker."""
        async with self._lock:
            if self._state is State.HALF_OPEN:
                self._close()
            else:
                self._failures = 0

    async def record_failure(self) -> None:
        """Record a failed attempt; may trip the breaker OPEN."""
        async with self._lock:
            self._failures += 1
            if self._state is State.HALF_OPEN:
                self._trip_open()
            elif self._state is State.CLOSED and self._failures >= self.failure_threshold:
                self._trip_open()

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        blocking: bool = True,
        **kwargs: Any,
    ) -> T:
        """Run ``func`` under the breaker's protection.

        With ``blocking=True`` (default) waits via :meth:`acquire` until an
        attempt is admitted. With ``blocking=False``, raises
        :class:`CircuitBreakerOpen` immediately instead of waiting.
        Successes and failures of ``func`` are recorded automatically; the
        original exception is re-raised on failure.
        """
        if blocking:
            await self.acquire()
        else:
            async with self._lock:
                self._refresh()
                if self._state is State.OPEN:
                    raise CircuitBreakerOpen(
                        f"breaker {self.name} is OPEN; "
                        f"retry in {self.recovery_timeout}s"
                    )
                if self._state is State.HALF_OPEN:
                    if self._probe_active:
                        raise CircuitBreakerOpen(
                            f"breaker {self.name} probe already in flight"
                        )
                    self._probe_active = True
                    self._gate.clear()
        try:
            result = await func(*args, **kwargs)
        except Exception:
            await self.record_failure()
            raise
        await self.record_success()
        return result

    def reset(self) -> None:
        """Force the breaker back to CLOSED with a clean failure count."""
        self._state = State.CLOSED
        self._failures = 0
        self._probe_active = False
        self._gate.set()
