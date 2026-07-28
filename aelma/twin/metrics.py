"""MetricsCollector: stdlib-only metrics for the AELMA twin.

Pure-Python counters, gauges, and dict-based histograms (built on
:class:`collections.Counter` and plain dicts), with a Prometheus
text-format exporter and a minimal asyncio HTTP ``/metrics`` endpoint.
No external dependencies.

Standard AELMA metric names are exported as module constants:

* ``PACKETS_RECEIVED``        counter — telemetry packets ingested
* ``ACTIONS_FIRED``           counter — A2A actions logged (label: action)
* ``WEBSOCKET_CONNECTIONS``   gauge   — currently connected viewers
* ``MEMORY_BYTES``            gauge   — process RSS, refreshed on scrape
* ``PACKET_HANDLING_SECONDS`` histogram — time spent in handle_packet
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from collections import Counter
from typing import Any, Callable

log = logging.getLogger("aelma.twin.metrics")

# Standard metric names.
PACKETS_RECEIVED = "aelma_packets_received_total"
ACTIONS_FIRED = "aelma_actions_fired_total"
WEBSOCKET_CONNECTIONS = "aelma_websocket_connections"
MEMORY_BYTES = "aelma_memory_bytes"
PACKET_HANDLING_SECONDS = "aelma_packet_handling_seconds"

# Prometheus client default buckets (seconds).
DEFAULT_HISTOGRAM_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)

# A label set is stored canonically as a sorted tuple of (key, value).
LabelsKey = tuple[tuple[str, str], ...]


def _labels_key(labels: dict[str, str] | None) -> LabelsKey:
    """Canonicalize a labels dict into a hashable, sorted tuple."""
    if not labels:
        return ()
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


def _escape_label_value(value: str) -> str:
    """Escape a label value per the Prometheus text format spec."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(key: LabelsKey, extra: tuple[str, str] | None = None) -> str:
    """Render a canonical label key (plus one optional extra pair) as
    the ``{k="v",...}`` suffix, or "" when there are no labels."""
    pairs = list(key)
    if extra is not None:
        pairs.append(extra)
    if not pairs:
        return ""
    inner = ",".join(f'{k}="{_escape_label_value(v)}"' for k, v in pairs)
    return "{" + inner + "}"


def _read_rss_bytes() -> int | None:
    """Best-effort resident memory of this process, in bytes.

    Uses ``resource`` on POSIX (Linux ru_maxrss is KiB, macOS is bytes)
    and the Win32 API via ctypes on Windows. Returns None when neither
    is available.
    """
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(  # type: ignore[attr-defined]
                ctypes.windll.kernel32.GetCurrentProcess(),  # type: ignore[attr-defined]
                ctypes.byref(counters),
                counters.cb,
            )
            return int(counters.WorkingSetSize) if ok else None
        except Exception:  # pragma: no cover - defensive
            return None
    try:
        import resource

        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return rss if sys.platform == "darwin" else rss * 1024
    except ImportError:  # pragma: no cover - non-POSIX, non-Windows
        return None


class _Histogram:
    """Dict-based histogram: cumulative bucket counts plus sum/count.

    ``series`` maps a canonical label key to
    ``{"buckets": [cumulative counts per finite bucket], "sum": x, "count": n}``.
    The implicit ``+Inf`` bucket always equals ``count``.
    """

    def __init__(self, buckets: tuple[float, ...]) -> None:
        self.buckets = tuple(sorted(float(b) for b in buckets))
        self.series: dict[LabelsKey, dict[str, Any]] = {}

    def observe(self, key: LabelsKey, value: float) -> None:
        entry = self.series.setdefault(
            key, {"buckets": [0] * len(self.buckets), "sum": 0.0, "count": 0}
        )
        for i, bound in enumerate(self.buckets):
            if value <= bound:
                entry["buckets"][i] += 1
        entry["sum"] += value
        entry["count"] += 1

    def snapshot(self, key: LabelsKey) -> dict[str, Any]:
        """Non-cumulative view: ``{le_bound: count, ..., "sum": s, "count": n}``."""
        entry = self.series.get(key)
        if entry is None:
            return {"sum": 0.0, "count": 0}
        cum = entry["buckets"]
        out: dict[str, Any] = {"sum": entry["sum"], "count": entry["count"]}
        prev = 0
        for bound, c in zip(self.buckets, cum):
            out[bound] = c - prev
            prev = c
        out[float("inf")] = entry["count"] - prev
        return out


class MetricsCollector:
    """Registry of counters, gauges, and histograms with Prometheus export.

    All ``increment``/``set_gauge``/``observe`` calls auto-register the
    metric on first use; call the ``register_*`` methods first if you want
    HELP text or custom histogram buckets.
    """

    def __init__(
        self, memory_reader: Callable[[], int | None] | None = None
    ) -> None:
        self._counters: dict[str, Counter[LabelsKey]] = {}
        self._gauges: dict[str, dict[LabelsKey, float]] = {}
        self._histograms: dict[str, _Histogram] = {}
        self._help: dict[str, str] = {}
        self._memory_reader = memory_reader or _read_rss_bytes

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    def register_counter(self, name: str, help: str = "") -> None:
        self._counters.setdefault(name, Counter())
        if help:
            self._help[name] = help

    def register_gauge(self, name: str, help: str = "") -> None:
        self._gauges.setdefault(name, {})
        if help:
            self._help[name] = help

    def register_histogram(
        self,
        name: str,
        buckets: tuple[float, ...] | None = None,
        help: str = "",
    ) -> None:
        self._histograms.setdefault(
            name, _Histogram(buckets or DEFAULT_HISTOGRAM_BUCKETS)
        )
        if help:
            self._help[name] = help

    # ------------------------------------------------------------------ #
    # Counters
    # ------------------------------------------------------------------ #
    def increment(
        self,
        name: str,
        amount: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Add ``amount`` to a counter series (default 1)."""
        if name not in self._counters:
            self.register_counter(name)
        self._counters[name][_labels_key(labels)] += amount

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Current counter value for a series; 0 if never incremented."""
        return self._counters.get(name, Counter()).get(_labels_key(labels), 0.0)

    # ------------------------------------------------------------------ #
    # Gauges
    # ------------------------------------------------------------------ #
    def set_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Set a gauge series to an absolute value."""
        if name not in self._gauges:
            self.register_gauge(name)
        self._gauges[name][_labels_key(labels)] = float(value)

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Current gauge value for a series; 0 if never set."""
        return self._gauges.get(name, {}).get(_labels_key(labels), 0.0)

    # ------------------------------------------------------------------ #
    # Histograms
    # ------------------------------------------------------------------ #
    def observe(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Record one observation into a histogram (default buckets)."""
        if name not in self._histograms:
            self.register_histogram(name)
        self._histograms[name].observe(_labels_key(labels), float(value))

    def histogram_snapshot(
        self, name: str, labels: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Snapshot one histogram series: per-bucket counts, sum, count."""
        hist = self._histograms.get(name)
        if hist is None:
            return {"sum": 0.0, "count": 0}
        return hist.snapshot(_labels_key(labels))

    # ------------------------------------------------------------------ #
    # Memory gauge
    # ------------------------------------------------------------------ #
    def update_memory_gauge(self) -> None:
        """Refresh the ``aelma_memory_bytes`` gauge from the memory reader."""
        rss = self._memory_reader()
        if rss is not None:
            self.set_gauge(MEMORY_BYTES, rss)

    # ------------------------------------------------------------------ #
    # Snapshots / export
    # ------------------------------------------------------------------ #
    def snapshot(self) -> dict[str, Any]:
        """Plain-dict snapshot of every metric, for in-process consumers."""
        return {
            "counters": {
                name: {repr(k): v for k, v in series.items()}
                for name, series in self._counters.items()
            },
            "gauges": {
                name: {repr(k): v for k, v in series.items()}
                for name, series in self._gauges.items()
            },
            "histograms": {
                name: {repr(k): hist.snapshot(k) for k in hist.series}
                for name, hist in self._histograms.items()
            },
        }

    def export_prometheus(self) -> str:
        """Render all metrics in the Prometheus text exposition format."""
        lines: list[str] = []

        def header(name: str, mtype: str) -> None:
            lines.append(f"# HELP {name} {self._help.get(name, '')}")
            lines.append(f"# TYPE {name} {mtype}")

        for name in sorted(self._counters):
            header(name, "counter")
            for key, value in sorted(self._counters[name].items()):
                lines.append(f"{name}{_format_labels(key)} {value:g}")
        for name in sorted(self._gauges):
            header(name, "gauge")
            for key, value in sorted(self._gauges[name].items()):
                lines.append(f"{name}{_format_labels(key)} {value:g}")
        for name in sorted(self._histograms):
            header(name, "histogram")
            hist = self._histograms[name]
            for key in sorted(hist.series):
                entry = hist.series[key]
                for bound, cum in zip(hist.buckets, entry["buckets"]):
                    lines.append(
                        f"{name}_bucket"
                        f'{_format_labels(key, ("le", f"{bound:g}"))} {cum}'
                    )
                lines.append(
                    f"{name}_bucket"
                    f'{_format_labels(key, ("le", "+Inf"))} {entry["count"]}'
                )
                lines.append(f"{name}_sum{_format_labels(key)} {entry['sum']:g}")
                lines.append(f"{name}_count{_format_labels(key)} {entry['count']}")
        return "\n".join(lines) + "\n"


async def serve_metrics(
    collector: MetricsCollector, host: str = "0.0.0.0", port: int = 9090
) -> asyncio.Server:
    """Serve ``GET /metrics`` in Prometheus text format over plain HTTP.

    Returns the running :class:`asyncio.Server`; the caller owns its
    lifecycle (``server.close(); await server.wait_closed()``).
    """

    async def handle(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            # Drain request headers.
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if line in (b"\r\n", b"\n", b""):
                    break
            parts = request_line.decode("latin-1").split()
            method, path = (parts + ["", ""])[:2]
            if method == "GET" and path.split("?", 1)[0] == "/metrics":
                collector.update_memory_gauge()
                body = collector.export_prometheus().encode("utf-8")
                status = "200 OK"
                content_type = "text/plain; version=0.0.4; charset=utf-8"
            else:
                body = b"not found\n"
                status = "404 Not Found"
                content_type = "text/plain; charset=utf-8"
            writer.write(
                f"HTTP/1.1 {status}\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n".encode("latin-1")
                + body
            )
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError, OSError) as exc:
            log.debug("metrics endpoint connection dropped: %s", exc)
        finally:
            writer.close()

    server = await asyncio.start_server(handle, host, port)
    bound = server.sockets[0].getsockname() if server.sockets else (host, port)
    log.info("metrics endpoint listening on http://%s:%s/metrics", *bound[:2])
    return server
