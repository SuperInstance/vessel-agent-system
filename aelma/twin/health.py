"""HealthChecker: HTTP health/readiness/liveness endpoints for the twin.

Exposes a minimal asyncio HTTP server (stdlib only — the twin already runs
an event loop, so a raw :func:`asyncio.start_server` handler is enough)
with three endpoints:

* ``GET /health`` — overall status plus per-component details
  (``websocket``, ``log_files``, ``memory``). 200 when no component has
  failed, 503 when any component reports ``fail``.
* ``GET /ready`` — readiness probe: 200 only when nothing has failed and
  the bridge WebSocket is connected; 503 otherwise.
* ``GET /live`` — liveness probe: always 200 while the process and its
  event loop are alive; reports uptime.

Component statuses are ``ok``, ``degraded``, or ``fail``; the overall
status maps to ``healthy``, ``degraded``, or ``unhealthy``.

Stdlib only (psutil/resource are used opportunistically for RSS when
available, but neither is required).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .circuit_breaker import State

if TYPE_CHECKING:  # avoid a runtime import cycle with twin.core
    from .core import TwinCore

log = logging.getLogger("aelma.twin.health")

#: Component status values.
OK = "ok"
DEGRADED = "degraded"
FAIL = "fail"


def _process_rss_bytes() -> int | None:
    """Best-effort resident set size of this process, or None if unknown.

    Tries psutil first, then the stdlib ``resource`` module (Unix only).
    """
    try:
        import psutil  # type: ignore

        return int(psutil.Process().memory_info().rss)
    except ImportError:
        pass
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KiB, macOS bytes; assume KiB unless clearly bytes.
        return int(rss * 1024) if rss < 1 << 40 else int(rss)
    except (ImportError, OSError, ValueError):
        return None


def _writable_error(path: Path) -> str | None:
    """Return a human error string if ``path`` is not writable, else None.

    Walks up to the nearest existing ancestor so not-yet-created log
    files are judged by the directory they will be written into.
    """
    target = path
    while not target.exists():
        parent = target.parent
        if parent == target:
            return f"{path}: no existing ancestor"
        target = parent
    if target == path and target.is_dir():
        return f"{path} is a directory, not a file"
    if not os.access(target, os.W_OK):
        return f"{target} is not writable"
    return None


class HealthChecker:
    """Component health checks plus a tiny asyncio HTTP server.

    Parameters
    ----------
    core:
        The :class:`~twin.core.TwinCore` instance to inspect.
    host:
        Bind address for the HTTP server.
    port:
        TCP port for the HTTP server. Use 0 for an ephemeral port (tests).
    memory_limit_mb:
        RSS threshold in MiB above which the memory component reports
        ``degraded``.
    rss_probe:
        Override for the RSS measurement (tests); defaults to
        :func:`_process_rss_bytes`.
    """

    def __init__(
        self,
        core: "TwinCore",
        host: str = "0.0.0.0",
        port: int = 8091,
        memory_limit_mb: float = 512.0,
        rss_probe: Callable[[], int | None] | None = None,
    ) -> None:
        self.core = core
        self.host = host
        self.port = port
        self.memory_limit_mb = memory_limit_mb
        self._rss_probe = rss_probe or _process_rss_bytes
        self._server: asyncio.AbstractServer | None = None
        self._started_at = time.time()

    # ------------------------------------------------------------------ #
    # Component checks
    # ------------------------------------------------------------------ #
    def check_websocket(self) -> dict[str, Any]:
        """Bridge WebSocket connectivity, via TwinCore + its breaker."""
        breaker = self.core.bridge_breaker
        connected = self.core.bridge_connected
        if connected and breaker.state is State.CLOSED:
            status = OK
        elif breaker.state is State.OPEN:
            status = FAIL
        else:
            # Not connected but the breaker still admits retries.
            status = DEGRADED
        return {
            "status": status,
            "connected": connected,
            "bridge_url": self.core.bridge_url,
            "breaker": breaker.stats(),
            "viewers": len(self.core._viewers),
        }

    def check_log_files(self) -> dict[str, Any]:
        """Writability of the A2A action log and bathymetry persist path."""
        details: dict[str, Any] = {}
        worst = OK
        if self.core.a2a_log.closed:
            details["a2a_log"] = {"status": FAIL, "error": "log is closed"}
            worst = FAIL
        else:
            err = _writable_error(self.core.a2a_log_path)
            details["a2a_log"] = {
                "status": FAIL if err else OK,
                "path": str(self.core.a2a_log_path),
            }
            if err:
                details["a2a_log"]["error"] = err
                worst = FAIL
        err = _writable_error(self.core.bathymetry_path)
        details["bathymetry"] = {
            "status": FAIL if err else OK,
            "path": str(self.core.bathymetry_path),
        }
        if err:
            details["bathymetry"]["error"] = err
            worst = FAIL
        return {"status": worst, **details}

    def check_memory(self) -> dict[str, Any]:
        """Process RSS against the configured limit."""
        rss = self._rss_probe()
        result: dict[str, Any] = {"limit_mb": self.memory_limit_mb}
        if rss is None:
            # Can't measure — don't fail health for a missing probe.
            result.update(status=OK, rss_mb=None, note="rss unavailable")
            return result
        rss_mb = rss / (1024 * 1024)
        result["rss_mb"] = round(rss_mb, 1)
        result["status"] = DEGRADED if rss_mb > self.memory_limit_mb else OK
        return result

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #
    def components(self) -> dict[str, dict[str, Any]]:
        """Run every component check and return them keyed by name."""
        return {
            "websocket": self.check_websocket(),
            "log_files": self.check_log_files(),
            "memory": self.check_memory(),
        }

    @staticmethod
    def _worst_status(components: dict[str, dict[str, Any]]) -> str:
        statuses = {c["status"] for c in components.values()}
        if FAIL in statuses:
            return FAIL
        if DEGRADED in statuses:
            return DEGRADED
        return OK

    def health_report(self) -> tuple[int, dict[str, Any]]:
        """Full health report; HTTP 503 when any component failed."""
        comps = self.components()
        worst = self._worst_status(comps)
        overall = {OK: "healthy", DEGRADED: "degraded", FAIL: "unhealthy"}[worst]
        body = {
            "status": overall,
            "vessel_id": self.core.vessel_id,
            "uptime_s": round(time.time() - self._started_at, 1),
            "components": comps,
        }
        return (503 if worst == FAIL else 200), body

    def ready_report(self) -> tuple[int, dict[str, Any]]:
        """Readiness report; 503 unless nothing failed and WS is connected."""
        comps = self.components()
        ws_ok = comps["websocket"]["status"] == OK
        no_fail = all(c["status"] != FAIL for c in comps.values())
        ready = ws_ok and no_fail
        return (200 if ready else 503), {
            "status": "ready" if ready else "not_ready",
            "components": comps,
        }

    def live_report(self) -> tuple[int, dict[str, Any]]:
        """Liveness report: the event loop answered, so the process lives."""
        return 200, {
            "status": "alive",
            "uptime_s": round(time.time() - self._started_at, 1),
        }

    # ------------------------------------------------------------------ #
    # HTTP server
    # ------------------------------------------------------------------ #
    _ROUTES = {
        "/health": health_report,
        "/ready": ready_report,
        "/live": live_report,
    }

    async def start(self) -> None:
        """Bind the HTTP server. Idempotent."""
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        sock = self._server.sockets[0]
        self.port = sock.getsockname()[1]
        log.info("health HTTP server listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Close the HTTP server."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            # Drain headers; bodies are not expected on health probes.
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if line in (b"\r\n", b"\n", b""):
                    break
            try:
                method, target, _ = request_line.decode("latin-1").split()
            except ValueError:
                self._respond(writer, 400, {"status": "bad_request"})
                return
            path = target.split("?", 1)[0]
            handler = self._ROUTES.get(path)
            if handler is None:
                self._respond(writer, 404, {"status": "not_found", "path": path})
                return
            if method != "GET":
                self._respond(writer, 405, {"status": "method_not_allowed"})
                return
            code, body = handler(self)
            self._respond(writer, code, body)
        except (asyncio.TimeoutError, ConnectionError) as exc:
            log.debug("health connection dropped: %s", exc)
        finally:
            writer.close()

    @staticmethod
    def _respond(
        writer: asyncio.StreamWriter, code: int, body: dict[str, Any]
    ) -> None:
        payload = json.dumps(body, default=str).encode("utf-8")
        reason = {200: "OK", 400: "Bad Request", 404: "Not Found",
                  405: "Method Not Allowed", 503: "Service Unavailable"}[code]
        writer.write(
            f"HTTP/1.1 {code} {reason}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            f"Connection: close\r\n"
            f"\r\n".encode("latin-1")
            + payload
        )
