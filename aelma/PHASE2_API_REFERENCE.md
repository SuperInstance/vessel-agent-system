# AELMA Phase 2 — Complete API Reference

**Version:** 2.0.0
**Last Updated:** 2026-07-27
**Status:** Production Ready

---

## Table of Contents

- [Overview](#overview)
- [Twin Core API](#twin-core-api)
- [Watcher Registry API](#watcher-registry-api)
- [A2A Log API](#a2a-log-api)
- [A2A Query API](#a2a-query-api)
- [Signal K API](#signal-k-api)
- [Telemetry Query API](#telemetry-query-api)
- [Health Checker API](#health-checker-api)
- [Metrics Collector API](#metrics-collector-api)
- [Circuit Breaker API](#circuit-breaker-api)
- [Stratified Sampler API](#stratified-sampler-api)
- [LLM Narrator API](#llm-narrator-api)
- [HTTP Endpoints](#http-endpoints)
- [WebSocket Protocol](#websocket-protocol)
- [Data Schemas](#data-schemas)

---

## Overview

AELMA Phase 2 provides a comprehensive API for marine telemetry ingestion, processing, alerting, and querying. All APIs are designed with:

- **Asyncio-first** — All I/O operations are async
- **Type-hinted** — Full Python type annotations
- **Validated** — Schema-based input validation
- **Tested** — 407 tests covering all APIs

### API Modules

```
aelma/
├── twin/
│   ├── core.py              # TwinCore API
│   ├── watchers.py          # WatcherRegistry API
│   ├── a2a_log.py           # A2ALog API
│   ├── a2a_query.py         # A2AQuery API
│   ├── telemetry_query.py  # TelemetryQuery API
│   ├── health.py            # HealthChecker API
│   ├── metrics.py           # MetricsCollector API
│   ├── circuit_breaker.py   # CircuitBreaker API
│   ├── stratified_sampler.py # StratifiedSampler API
│   └── llm_narrator.py      # LLMNarrator API
├── bridge/
│   └── signalk.py           # Signal K API
└── viewer/
    └── dashboard.html       # Dashboard WebSocket API
```

---

## Twin Core API

### Module: `twin.core`

**Purpose:** Core vessel state management, packet handling, and component coordination.

#### Class: `TwinCore`

```python
class TwinCore:
    """Core twin system coordinating all Phase 2 components."""

    def __init__(
        self,
        vessel_id: str,
        bridge_url: str,
        viewer_port: int,
        *,
        health_port: int = 8091,
        metrics_port: int = 9090,
        a2a_log_path: str | Path = "logs/a2a.jsonl",
        bathymetry_path: str | Path = "data/bathymetry.json",
        memory_limit_mb: float = 512.0,
    ) -> None:
        """Initialize TwinCore with all Phase 2 components.

        Parameters
        ----------
        vessel_id:
            Unique identifier for this vessel (e.g., "FV-EILEEN").
        bridge_url:
            WebSocket URL of the bridge (ws://localhost:8000).
        viewer_port:
            TCP port for viewer WebSocket server.
        health_port:
            TCP port for health HTTP server (default 8091).
        metrics_port:
            TCP port for metrics HTTP server (default 9090).
        a2a_log_path:
            Path to A2A action log file.
        bathymetry_path:
            Path to bathymetry persistence file.
        memory_limit_mb:
            RSS threshold for degraded health status.
        """
```

#### Methods

##### `start`

```python
async def start(self) -> None:
    """Start all twin services.

        * Connect to bridge WebSocket
        * Start viewer WebSocket server
        * Start health HTTP server
        * Start metrics HTTP server
        * Start watcher evaluation loop
    """
```

##### `stop`

```python
async def stop(self) -> None:
    """Stop all twin services gracefully.

        * Close viewer connections
        * Close bridge connection
        * Stop health server
        * Stop metrics server
        * Flush A2A log
        * Persist bathymetry
    """
```

##### `handle_packet`

```python
async def handle_packet(self, packet: TelemetryPacket) -> None:
    """Process a telemetry packet through the full pipeline.

        Pipeline stages:
        1. Update vessel state
        2. Evaluate watcher rules
        3. Log A2A actions
        4. Broadcast to viewers
        5. Update metrics

        Parameters
        ----------
        packet:
            Telemetry packet from bridge.
    """
```

##### `add_watcher`

```python
def add_watcher(self, rule: Mapping[str, Any] | WatcherRule) -> str:
    """Add a watcher rule to the registry.

        Parameters
        ----------
        rule:
            Watcher rule specification.

        Returns
        -------
        str
            Rule ID.
    """
```

##### `remove_watcher`

```python
def remove_watcher(self, rule_id: str) -> bool:
    """Remove a watcher rule by ID.

        Parameters
        ----------
        rule_id:
            Rule identifier.

        Returns
        -------
        bool
            True if rule existed and was removed.
    """
```

##### `query_actions`

```python
async def query_actions(
    self,
    *,
    start_ts: datetime | None = None,
    end_ts: datetime | None = None,
    action: str | None = None,
    min_priority: float | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query the A2A log for historical actions.

        Parameters
        ----------
        start_ts:
            Start of time range (inclusive).
        end_ts:
            End of time range (inclusive).
        action:
            Filter by action name.
        min_priority:
            Minimum priority threshold.
        limit:
            Maximum results to return.

        Returns
        -------
        list[dict]
            Matching action records.
    """
```

##### `query_telemetry`

```python
async def query_telemetry(
    self,
    channels: list[str],
    start: datetime,
    end: datetime,
    *,
    downsample_to: int | None = None,
    aggregate: str | None = None,
) -> dict[str, list[tuple[datetime, Any]]]:
    """Query historical telemetry data.

        Parameters
        ----------
        channels:
            List of channel names (e.g., ["depth_m", "position.lat"]).
        start:
            Start of time range.
        end:
            End of time range.
        downsample_to:
            Target seconds per data point (None = all data).
        aggregate:
            Aggregation function: "min", "max", "avg", "sum".

        Returns
        -------
        dict
            Channel names mapped to (timestamp, value) tuples.
    """
```

#### Properties

##### `state`

```python
@property
def state(self) -> VesselState:
    """Current vessel state."""
```

##### `watchers`

```python
@property
def watchers(self) -> WatcherRegistry:
    """Watcher registry instance."""
```

##### `a2a_log`

```python
@property
def a2a_log(self) -> A2ALog:
    """A2A log instance."""
```

##### `health`

```python
@property
def health(self) -> HealthChecker:
    """Health checker instance."""
```

##### `metrics`

```python
@property
def metrics(self) -> MetricsCollector:
    """Metrics collector instance."""
```

---

## Watcher Registry API

### Module: `twin.watchers`

**Purpose:** Deterministic threshold rules for alert generation.

#### Class: `WatcherRegistry`

```python
class WatcherRegistry:
    """Registry of watcher rules with cooldown suppression."""

    def __init__(
        self,
        *,
        verbose: bool = False,
        history: WatcherHistory | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize watcher registry.

        Parameters
        ----------
        verbose:
            Log every firing at INFO level.
        history:
            Optional WatcherHistory for cooldown tracking.
        now:
            Clock function (injected for testing).
        """
```

#### Methods

##### `add`

```python
def add(self, rule: Mapping[str, Any] | WatcherRule) -> str:
    """Validate, normalize, and register a rule.

        Parameters
        ----------
        rule:
            Rule specification or WatcherRule instance.

        Returns
        -------
        str
            Rule ID.

        Raises
        ------
        ValueError
            If rule ID is duplicate or action is not allowed.
        TypeError
            If rule structure is invalid.
    """
```

##### `remove`

```python
def remove(self, rule_id: str) -> bool:
    """Unregister a rule by ID.

        Parameters
        ----------
        rule_id:
            Rule identifier.

        Returns
        -------
        bool
            True if rule existed.
    """
```

##### `evaluate`

```python
def evaluate(self, frame: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Evaluate all rules against a frame.

        Parameters
        ----------
        frame:
            Current state frame (mapping of field names to values).

        Returns
        -------
        list[dict]
            Fired actions, in registration order.

        Raises
        ------
        TypeError
            If frame is not a mapping.
    """
```

##### `on`

```python
def on(self, event: str, callback: Callable[..., Any]) -> None:
    """Subscribe to events.

        Parameters
        ----------
        event:
            Event name: "fired", "suppressed", "error".
        callback:
            Callback function.

        Raises
        ------
        ValueError
            If event name is unknown.
    """
```

#### Events

##### `fired`

Emitted when a rule fires and passes cooldown suppression.

**Callback signature:**
```python
def on_fired(action: dict[str, Any]) -> None:
    """Called with action dict."""
```

##### `suppressed`

Emitted when a rule matches but is suppressed by cooldown.

**Callback signature:**
```python
def on_suppressed(rule_id: str, reason: str) -> None:
    """Called with rule ID and suppression reason."""
```

##### `error`

Emitted when rule evaluation fails.

**Callback signature:**
```python
def on_error(exc: Exception, context: dict[str, Any]) -> None:
    """Called with exception and context dict."""
```

#### Rule Schema

```python
{
    "id": "shallow-water",                    # Required: unique string
    "name": "Shallow water warning",          # Required: display name
    "when": lambda f: f.get("depth_m") < 2.0, # Required: predicate callable
    "action": {                                # Required: action specification
        "name": "raise_alert",                 # Allowed action name
        "payload": lambda f: {...},            # Optional: payload callable
        "reason": lambda f: "...",             # Optional: reason callable
        "priority": lambda f: 0.85,            # Optional: priority callable
    },
    "cooldown_s": 30.0,                        # Optional: cooldown seconds
}
```

#### Allowed Actions

```python
ALLOWED_ACTIONS = frozenset({
    "morph_to_hazard_mode",
    "morph_to_navigation_mode",
    "morph_to_engineering_mode",
    "highlight_waypoint",
    "raise_alert",
    "clear_alerts",
    "set_panel_focus",
    "announce",
})
```

#### Usage Example

```python
import asyncio
from twin.watchers import WatcherRegistry
from twin.watcher_history import WatcherHistory

# Create registry with history
registry = WatcherRegistry(
    history=WatcherHistory(max_memory=1000),
    verbose=True
)

# Add a shallow water warning
registry.add({
    "id": "shallow-water",
    "name": "Shallow water warning",
    "when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
    "action": {
        "name": "raise_alert",
        "payload": lambda f: {"kind": "shallow_water", "depth": f["depth_m"]},
        "reason": lambda f: f"depth={f['depth_m']:.2f}m",
        "priority": lambda f: 0.85,
    },
    "cooldown_s": 30.0,
})

# Subscribe to events
def on_fired(action):
    print(f"Alert fired: {action}")

registry.on("fired", on_fired)

# Evaluate a frame
frame = {"depth_m": 1.5, "speed_kn": 5.0}
actions = registry.evaluate(frame)

print(f"Fired {len(actions)} actions")
```

---

## A2A Log API

### Module: `twin.a2a_log`

**Purpose:** Append-only audit trail of all agent-to-agent actions.

#### Class: `A2ALog`

```python
class A2ALog:
    """Asyncio-safe append-only JSONL log."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int | None = None,
        keep: int = 5,
    ) -> None:
        """Initialize A2A log.

        Parameters
        ----------
        path:
            Path to JSONL log file.
        max_bytes:
            Rotate log after this size (None = no rotation).
        keep:
            Number of rotated files to keep.
        """
```

#### Methods

##### `append`

```python
async def append(
    self,
    action: str,
    payload: Mapping[str, Any] | None = None,
    *,
    source: str = "system",
    reason: str = "",
    priority: float = DEFAULT_PRIORITY,
    ts: Any = None,
) -> dict[str, Any]:
    """Append an action record to the log.

        Parameters
        ----------
        action:
            Action name (non-empty string).
        payload:
            Action payload (mapping or None).
        source:
            Action origin: "watcher", "llm", "crew", "system".
        reason:
            Human-readable reason (may be empty).
        priority:
            Priority value 0.0-1.0.
        ts:
            Timestamp (None = now, datetime = ISO, number = epoch seconds).

        Returns
        -------
        dict
            Complete record as written (includes _loggedAt, _seq).

        Raises
        ------
        RuntimeError
            If append after close().
        ValueError
            If validation fails.
        TypeError
            If types are invalid.
    """
```

##### `close`

```python
async def close(self) -> None:
    """Mark the log closed. Future appends raise RuntimeError."""
```

##### `stats`

```python
async def stats(self) -> dict[str, Any]:
    """Get log statistics.

        Returns
        -------
        dict
            {path, records, closed, size_bytes, max_bytes, keep}
    """
```

#### Properties

##### `path`

```python
@property
def path(self) -> Path:
    """Log file path."""
```

##### `seq`

```python
@property
def seq(self) -> int:
    """Sequence number for next record."""
```

##### `closed`

```python
@property
def closed(self) -> bool:
    """Whether log is closed."""
```

#### Record Format

```python
{
    "kind": "action",                          # Record kind
    "action": "raise_alert",                   # Action name
    "payload": {"kind": "shallow_water"},      # Action payload
    "source": "watcher",                       # Action origin
    "reason": "depth=1.40m",                   # Human reason
    "priority": 0.85,                          # Priority 0.0-1.0
    "ts": "2026-07-27T15:04:23.181000+00:00", # Action time
    "_loggedAt": "2026-07-27T15:04:23.204112+00:00", # Write time
    "_seq": 42,                                 # Monotonic sequence
}
```

#### Usage Example

```python
import asyncio
from twin.a2a_log import A2ALog
from datetime import datetime

async def main():
    # Create log with rotation
    log = A2ALog(
        "logs/a2a.jsonl",
        max_bytes=10_000_000,  # 10MB
        keep=5
    )

    # Append an action
    record = await log.append(
        action="raise_alert",
        payload={"kind": "shallow_water", "depth": 1.4},
        source="watcher",
        reason="depth=1.40m",
        priority=0.85,
        ts=datetime.now()
    )

    print(f"Logged action {record['_seq']}: {record['action']}")

    # Get stats
    stats = await log.stats()
    print(f"Log has {stats['records']} records")

    # Close log
    await log.close()

asyncio.run(main())
```

---

## A2A Query API

### Module: `twin.a2a_query`

**Purpose:** Query the A2A log for historical actions and patterns.

#### Class: `A2AQuery`

```python
class A2AQuery:
    """Query engine for A2A log files."""

    def __init__(
        self,
        log_path: str | Path,
        *,
        cache_size: int = 1000,
    ) -> None:
        """Initialize query engine.

        Parameters
        ----------
        log_path:
            Path to A2A log file (JSONL).
        cache_size:
            Maximum records to cache in memory.
        """
```

#### Methods

##### `search`

```python
async def search(
    self,
    *,
    start_ts: datetime | None = None,
    end_ts: datetime | None = None,
    action: str | None = None,
    source: str | None = None,
    min_priority: float | None = None,
    max_priority: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Search for action records matching criteria.

        Parameters
        ----------
        start_ts:
            Start timestamp (inclusive).
        end_ts:
            End timestamp (inclusive).
        action:
            Filter by action name.
        source:
            Filter by source (watcher, llm, crew, system).
        min_priority:
            Minimum priority threshold.
        max_priority:
            Maximum priority threshold.
        limit:
            Maximum results to return.
        offset:
            Number of results to skip.

        Returns
        -------
        list[dict]
            Matching action records, in chronological order.
    """
```

##### `aggregate_by_source`

```python
async def aggregate_by_source(
    self,
    *,
    start_ts: datetime | None = None,
    end_ts: datetime | None = None,
) -> dict[str, int]:
    """Count actions by source.

        Parameters
        ----------
        start_ts:
            Start timestamp (inclusive).
        end_ts:
            End timestamp (inclusive).

        Returns
        -------
        dict
            Source names mapped to counts.
    """
```

##### `aggregate_by_action`

```python
async def aggregate_by_action(
    self,
    *,
    start_ts: datetime | None = None,
    end_ts: datetime | None = None,
) -> dict[str, int]:
    """Count actions by type.

        Parameters
        ----------
        start_ts:
            Start timestamp (inclusive).
        end_ts:
            End timestamp (inclusive).

        Returns
        -------
        dict
            Action names mapped to counts.
    """
```

##### `get_high_priority_actions`

```python
async def get_high_priority_actions(
    self,
    *,
    start_ts: datetime | None = None,
    end_ts: datetime | None = None,
    threshold: float = 0.7,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get high-priority actions.

        Parameters
        ----------
        start_ts:
            Start timestamp (inclusive).
        end_ts:
            End timestamp (inclusive).
        threshold:
            Minimum priority (default 0.7).
        limit:
            Maximum results.

        Returns
        -------
        list[dict]
            High-priority action records.
    """
```

#### Usage Example

```python
import asyncio
from twin.a2a_query import A2AQuery
from datetime import datetime, timedelta

async def main():
    query = A2AQuery("logs/a2a.jsonl")

    # Search for alerts in last hour
    start = datetime.now() - timedelta(hours=1)
    results = await query.search(
        start_ts=start,
        action="raise_alert",
        min_priority=0.7,
        limit=100
    )

    print(f"Found {len(results)} high-priority alerts")

    # Aggregate by source
    source_counts = await query.aggregate_by_source(start_ts=start)
    print(f"Actions by source: {source_counts}")

    # Get high-priority actions
    high_pri = await query.get_high_priority_actions(
        start_ts=start,
        threshold=0.8,
        limit=20
    )
    print(f"High-priority actions: {len(high_pri)}")

asyncio.run(main())
```

---

## Signal K API

### Module: `bridge.signalk`

**Purpose:** Parse NMEA 2000 data via Signal K delta format.

#### Class: `SignalKDelta`

```python
class SignalKDelta:
    """Parser for Signal K delta messages."""

    def __init__(self, delta_data: dict[str, Any] | str):
        """Initialize parser.

        Parameters
        ----------
        delta_data:
            Parsed dict or JSON string of Signal K delta.
        """
```

#### Methods

##### `to_readings`

```python
def to_readings(self) -> list[Reading]:
    """Convert delta to AELMA telemetry readings.

        Returns
        -------
        list[dict]
            List of reading dicts with keys:
            - source: "signalk"
            - channel: AELMA channel name
            - value: Parsed value
            - path: Source path
    """
```

##### `get_context`

```python
def get_context(self) -> str:
    """Get vessel context (MMSI) from delta."""
```

##### `get_timestamp`

```python
def get_timestamp(self) -> str:
    """Get timestamp from delta."""
```

#### Module Functions

##### `parse_delta`

```python
def parse_delta(delta_data: dict[str, Any] | str) -> list[Reading]:
    """Convenience function: parse delta and return readings.

        Parameters
        ----------
        delta_data:
            Signal K delta (dict or JSON string).

        Returns
        -------
        list[dict]
            AELMA telemetry readings.
    """
```

##### `path_to_channel`

```python
def path_to_channel(path: str) -> str | None:
    """Convert Signal K path to AELMA channel name.

        Parameters
        ----------
        path:
            Signal K path (e.g., "navigation.depth.belowKeel").

        Returns
        -------
        str | None
            AELMA channel name or None if unsupported.
    """
```

##### `signalk_ws_endpoint`

```python
def signalk_ws_endpoint(host: str = "localhost", port: int = 3000) -> str:
    """Build Signal K WebSocket URL.

        Returns
        -------
        str
            WebSocket URL (e.g., "ws://localhost:3000/signalk/v1/stream")
    """
```

#### Supported Paths

| Signal K Path | AELMA Channel | Conversion |
|---------------|---------------|-------------|
| `navigation.position.latitude` | `position.lat` | None |
| `navigation.position.longitude` | `position.lon` | None |
| `navigation.speedOverGround` | `sog_kn` | m/s → knots |
| `navigation.courseOverGroundTrue` | `cog_deg` | None |
| `navigation.depth.*` | `depth_m` | None |
| `environment.wind.speedTrue` | `wind_kts_true` | m/s → knots |
| `environment.wind.speedApparent` | `wind_kts_apparent` | m/s → knots |
| `environment.wind.angleTrue` | `wind_dir_deg_true` | None |
| `environment.wind.angleApparent` | `wind_dir_deg_apparent` | None |
| `environment.water.temperature` | `sea_temp_c` | K → °C |
| `environment.air.temperature` | `air_temp_c` | K → °C |
| `environment.air.pressure` | `baro_mb` | Pa → mb |

#### Usage Example

```python
from bridge.signalk import parse_delta

# Example Signal K delta
delta = {
    "context": "vessels.urn:mrn:imo:mmsi:123456789",
    "updates": [{
        "timestamp": "2026-07-27T15:04:56Z",
        "values": [
            {"path": "navigation.depth.belowKeel", "value": 73.2},
            {"path": "environment.water.temperature", "value": 283.15}
        ]
    }]
}

# Parse to AELMA readings
readings = parse_delta(delta)

for reading in readings:
    print(f"{reading['channel']}: {reading['value']}")
# Output:
# depth_m: 73.2
# sea_temp_c: 10.0
```

---

## Telemetry Query API

### Module: `twin.telemetry_query`

**Purpose:** Query historical vessel state data with time ranges and aggregations.

#### Class: `TelemetryQuery`

```python
class TelemetryQuery:
    """Query engine for historical telemetry data."""

    def __init__(
        self,
        state: VesselState,
        *,
        max_points: int = 10000,
    ) -> None:
        """Initialize query engine.

        Parameters
        ----------
        state:
            VesselState instance with historical data.
        max_points:
            Maximum data points to return per query.
        """
```

#### Methods

##### `time_range`

```python
async def time_range(
    self,
    channels: list[str],
    start: datetime,
    end: datetime,
    *,
    downsample_to: int | None = None,
    aggregate: str | None = None,
    min_quality: str | None = None,
) -> dict[str, list[tuple[datetime, Any]]]:
    """Query telemetry over a time range.

        Parameters
        ----------
        channels:
            List of channel names (e.g., ["depth_m", "position.lat"]).
        start:
            Start of time range.
        end:
            End of time range.
        downsample_to:
            Target seconds per data point (None = all data).
        aggregate:
            Aggregation: "min", "max", "avg", "sum".
        min_quality:
            Minimum quality: "good", "fair", "poor", "bad".

        Returns
        -------
        dict
            Channel names mapped to (timestamp, value) tuples.
    """
```

##### `latest`

```python
async def latest(
    self,
    channels: list[str],
    *,
    max_age_ms: int = 5000,
) -> dict[str, tuple[datetime, Any]]:
    """Get latest values for channels.

        Parameters
        ----------
        channels:
            List of channel names.
        max_age_ms:
            Maximum data age in milliseconds.

        Returns
        -------
        dict
            Channel names mapped to (timestamp, value) tuples.
    """
```

##### `statistics`

```python
async def statistics(
    self,
    channel: str,
    start: datetime,
    end: datetime,
) -> dict[str, float]:
    """Get statistical summary for a channel.

        Parameters
        ----------
        channel:
            Channel name.
        start:
            Start of time range.
        end:
            End of time range.

        Returns
        -------
        dict
            {min, max, avg, sum, count, std_dev}
    """
```

#### Usage Example

```python
import asyncio
from twin.telemetry_query import TelemetryQuery
from datetime import datetime, timedelta

async def main():
    # Assume we have a VesselState instance
    query = TelemetryQuery(state)

    # Query depth for last hour, downsampled to 1 point/minute
    start = datetime.now() - timedelta(hours=1)
    results = await query.time_range(
        channels=["depth_m"],
        start=start,
        end=datetime.now(),
        downsample_to=60  # 1 point per minute
    )

    print(f"Retrieved {len(results['depth_m'])} depth points")

    # Get statistics
    stats = await query.statistics("depth_m", start, datetime.now())
    print(f"Depth stats: min={stats['min']:.1f}m, max={stats['max']:.1f}m")

    # Get latest values
    latest = await query.latest(["depth_m", "speed_kn", "sea_temp_c"])
    for channel, (ts, value) in latest.items():
        print(f"{channel}: {value} (age {datetime.now() - ts})")

asyncio.run(main())
```

---

## Health Checker API

### Module: `twin.health`

**Purpose:** HTTP health/readiness/liveness endpoints for Kubernetes integration.

#### Class: `HealthChecker`

```python
class HealthChecker:
    """Component health checks plus HTTP server."""

    def __init__(
        self,
        core: TwinCore,
        host: str = "0.0.0.0",
        port: int = 8091,
        memory_limit_mb: float = 512.0,
        rss_probe: Callable[[], int | None] | None = None,
    ) -> None:
        """Initialize health checker.

        Parameters
        ----------
        core:
            TwinCore instance to monitor.
        host:
            Bind address for HTTP server.
        port:
            TCP port for HTTP server (0 = ephemeral).
        memory_limit_mb:
            RSS threshold for degraded status.
        rss_probe:
            Override for RSS measurement (testing).
        """
```

#### Methods

##### `start`

```python
async def start(self) -> None:
    """Start HTTP server. Idempotent."""
```

##### `stop`

```python
async def stop(self) -> None:
    """Stop HTTP server."""
```

##### `components`

```python
def components(self) -> dict[str, dict[str, Any]]:
    """Run all component checks.

        Returns
        -------
        dict
            Component names mapped to status dicts.
    """
```

##### `health_report`

```python
def health_report(self) -> tuple[int, dict[str, Any]]:
    """Full health report.

        Returns
        -------
        tuple
            (HTTP status code, response body)
            200 when no failures, 503 when any component failed.
    """
```

##### `ready_report`

```python
def ready_report(self) -> tuple[int, dict[str, Any]]:
    """Readiness report.

        Returns
        -------
        tuple
            (HTTP status code, response body)
            200 only when ready, 503 otherwise.
    """
```

##### `live_report`

```python
def live_report(self) -> tuple[int, dict[str, Any]]:
    """Liveness report.

        Returns
        -------
        tuple
            (HTTP status code, response body)
            Always 200 if process is alive.
    """
```

#### Component Checks

##### `check_websocket`

```python
def check_websocket(self) -> dict[str, Any]:
    """Check bridge WebSocket connectivity.

        Returns
        -------
        dict
            {status, connected, bridge_url, breaker, viewers}
    """
```

##### `check_log_files`

```python
def check_log_files(self) -> dict[str, Any]:
    """Check log file writability.

        Returns
        -------
        dict
            {status, a2a_log, bathymetry}
    """
```

##### `check_memory`

```python
def check_memory(self) -> dict[str, Any]:
    """Check process RSS against limit.

        Returns
        -------
        dict
            {status, limit_mb, rss_mb, note?}
    """
```

#### HTTP Endpoints

##### `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "vessel_id": "FV-EILEEN",
  "uptime_s": 3600.5,
  "components": {
    "websocket": {
      "status": "ok",
      "connected": true,
      "bridge_url": "ws://localhost:8000",
      "breaker": {...},
      "viewers": 2
    },
    "log_files": {
      "status": "ok",
      "a2a_log": {...},
      "bathymetry": {...}
    },
    "memory": {
      "status": "degraded",
      "limit_mb": 512.0,
      "rss_mb": 520.3
    }
  }
}
```

##### `GET /ready`

**Response:**
```json
{
  "status": "ready",
  "components": {...}
}
```

##### `GET /live`

**Response:**
```json
{
  "status": "alive",
  "uptime_s": 3600.5
}
```

---

## Metrics Collector API

### Module: `twin.metrics`

**Purpose:** Prometheus metrics export for monitoring integration.

#### Class: `MetricsCollector`

```python
class MetricsCollector:
    """Registry of counters, gauges, and histograms."""

    def __init__(
        self,
        memory_reader: Callable[[], int | None] = None,
    ) -> None:
        """Initialize metrics collector.

        Parameters
        ----------
        memory_reader:
            Override for RSS measurement.
        """
```

#### Methods

##### `register_counter`

```python
def register_counter(self, name: str, help: str = "") -> None:
    """Register a counter metric.

        Parameters
        ----------
        name:
            Metric name (must be unique).
        help:
            Metric description (for HELP line).
    """
```

##### `register_gauge`

```python
def register_gauge(self, name: str, help: str = "") -> None:
    """Register a gauge metric.

        Parameters
        ----------
        name:
            Metric name (must be unique).
        help:
            Metric description (for HELP line).
    """
```

##### `register_histogram`

```python
def register_histogram(
    self,
    name: str,
    buckets: tuple[float, ...] | None = None,
    help: str = "",
) -> None:
    """Register a histogram metric.

        Parameters
        ----------
        name:
            Metric name (must be unique).
        buckets:
            Bucket boundaries (default Prometheus buckets).
        help:
            Metric description (for HELP line).
    """
```

##### `increment`

```python
def increment(
    self,
    name: str,
    amount: float = 1.0,
    labels: dict[str, str] | None = None,
) -> None:
    """Increment a counter.

        Parameters
        ----------
        name:
            Metric name.
        amount:
            Amount to add (default 1.0).
        labels:
            Label set (optional).
    """
```

##### `set_gauge`

```python
def set_gauge(
    self,
    name: str,
    value: float,
    labels: dict[str, str] | None = None,
) -> None:
    """Set a gauge to a value.

        Parameters
        ----------
        name:
            Metric name.
        value:
            Absolute value.
        labels:
            Label set (optional).
    """
```

##### `observe`

```python
def observe(
    self,
    name: str,
    value: float,
    labels: dict[str, str] | None = None,
) -> None:
    """Record an observation in a histogram.

        Parameters
        ----------
        name:
            Metric name.
        value:
            Observation value.
        labels:
            Label set (optional).
    """
```

##### `snapshot`

```python
def snapshot(self) -> dict[str, Any]:
    """Get snapshot of all metrics.

        Returns
        -------
        dict
            {counters: {...}, gauges: {...}, histograms: {...}}
    """
```

##### `export_prometheus`

```python
def export_prometheus(self) -> str:
    """Export metrics in Prometheus text format.

        Returns
        -------
        str
            Prometheus text exposition format.
    """
```

##### `update_memory_gauge`

```python
def update_memory_gauge(self) -> None:
    """Refresh the memory gauge from the memory reader."""
```

#### Standard Metric Names

```python
PACKETS_RECEIVED = "aelma_packets_received_total"
ACTIONS_FIRED = "aelma_actions_fired_total"
WEBSOCKET_CONNECTIONS = "aelma_websocket_connections"
MEMORY_BYTES = "aelma_memory_bytes"
PACKET_HANDLING_SECONDS = "aelma_packet_handling_seconds"
```

#### Module Function

##### `serve_metrics`

```python
async def serve_metrics(
    collector: MetricsCollector,
    host: str = "0.0.0.0",
    port: int = 9090,
) -> asyncio.Server:
    """Serve GET /metrics endpoint.

        Parameters
        ----------
        collector:
            MetricsCollector instance.
        host:
            Bind address.
        port:
            TCP port.

        Returns
        -------
        asyncio.Server
            Running server (caller owns lifecycle).
    """
```

#### Usage Example

```python
import asyncio
from twin.metrics import MetricsCollector, serve_metrics

async def main():
    # Create collector
    metrics = MetricsCollector()

    # Register metrics
    metrics.register_counter("aelma_packets_received_total", "Telemetry packets received")
    metrics.register_histogram("aelma_packet_handling_seconds", "Packet processing time")

    # Record metrics
    metrics.increment("aelma_packets_received_total")
    metrics.observe("aelma_packet_handling_seconds", 0.0023)

    # Export Prometheus format
    print(metrics.export_prometheus())

    # Serve HTTP endpoint
    server = await serve_metrics(metrics, port=9090)
    print("Metrics endpoint on http://localhost:9090/metrics")

    # Keep running
    await asyncio.sleep(3600)

    server.close()
    await server.wait_closed()

asyncio.run(main())
```

---

## Circuit Breaker API

### Module: `twin.circuit_breaker`

**Purpose:** Prevent cascade failures and enable automatic recovery.

#### Class: `CircuitBreaker`

```python
class CircuitBreaker:
    """Circuit breaker for resilient external calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_attempts: int = 1,
        *,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize circuit breaker.

        Parameters
        ----------
        failure_threshold:
            Failures before opening circuit.
        recovery_timeout:
            Seconds before attempting recovery.
        half_open_attempts:
            Allowed attempts in HALF_OPEN state.
        now:
            Clock function (injected for testing).
        """
```

#### Methods

##### `call`

```python
async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
    """Execute a function through the circuit breaker.

        Parameters
        ----------
        func:
            Async function to call.
        *args, **kwargs:
            Function arguments.

        Returns
        -------
        T
            Function return value.

        Raises
        ------
        CircuitOpenError
            If circuit is OPEN.
    """
```

##### `success`

```python
def success(self) -> None:
    """Record a successful call."""
```

##### `failure`

```python
def failure(self) -> None:
    """Record a failed call."""
```

##### `reset`

```python
def reset(self) -> None:
    """Reset circuit breaker to CLOSED state."""
```

#### Properties

##### `state`

```python
@property
def state(self) -> State:
    """Current circuit state (CLOSED, OPEN, HALF_OPEN)."""
```

##### `stats`

```python
@property
def stats(self) -> dict[str, Any]:
    """Circuit breaker statistics."""
```

#### Events

##### `on`

```python
def on(self, event: str, callback: Callable[..., Any]) -> None:
    """Subscribe to events.

        Events: "state_change", "success", "failure"
    """
```

#### Usage Example

```python
import asyncio
from twin.circuit_breaker import CircuitBreaker, CircuitOpenError

async def fetch_data():
    # Simulated external call
    await asyncio.sleep(0.1)
    return {"data": "value"}

async def main():
    breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=60.0
    )

    try:
        # Call through breaker
        result = await breaker.call(fetch_data)
        print(f"Success: {result}")
        breaker.success()
    except Exception as e:
        print(f"Failed: {e}")
        breaker.failure()

    # Check state
    print(f"State: {breaker.state}")
    print(f"Stats: {breaker.stats()}")

asyncio.run(main())
```

---

## Stratified Sampler API

### Module: `twin.stratified_sampler`

**Purpose:** Efficient depth-stratified bathymetry sampling with adaptive rates.

#### Class: `StratifiedSampler`

```python
class StratifiedSampler:
    """Depth-stratified bathymetry sampler."""

    def __init__(
        self,
        strata: list[tuple[float, float]],
        sampling_rates: dict[str, float],
        *,
        variance_threshold: float = 1.0,
    ) -> None:
        """Initialize sampler.

        Parameters
        ----------
        strata:
            List of (min_depth, max_depth) stratum boundaries.
        sampling_rates:
            Stratum names mapped to sampling rates (0.0-1.0).
        variance_threshold:
            Variance threshold for adaptive sampling.
        """
```

#### Methods

##### `add_sample`

```python
def add_sample(
    self,
    position: tuple[float, float],
    depth: float,
    confidence: float = 1.0,
) -> bool:
    """Add a depth sample if accepted by sampling strategy.

        Parameters
        ----------
        position:
            (lat, lon) tuple.
        depth:
            Depth value in meters.
        confidence:
            Confidence 0.0-1.0.

        Returns
        -------
        bool
            True if sample was accepted.
    """
```

##### `get_stratum`

```python
def get_stratum(self, depth: float) -> str:
    """Get stratum name for a depth value."""
```

##### `get_samples`

```python
def get_samples(
    self,
    stratum: str | None = None,
    bounds: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    """Get samples, optionally filtered.

        Parameters
        ----------
        stratum:
            Filter by stratum name (None = all).
        bounds:
            (min_lat, max_lat, min_lon, max_lon) bounds.

        Returns
        -------
        list[dict]
            Sample dicts with keys: position, depth, confidence, stratum.
    """
```

---

## LLM Narrator API

### Module: `twin.llm_narrator`

**Purpose:** Generate natural language descriptions of vessel state and events.

#### Class: `LLMNarrator`

```python
class LLMNarrator:
    """Natural language vessel state narrator."""

    def __init__(
        self,
        vessel_name: str,
        style: str = "concise",
        *,
        templates: dict[str, str] | None = None,
    ) -> None:
        """Initialize narrator.

        Parameters
        ----------
        vessel_name:
            Vessel name for narratives.
        style:
            Narrative style: "concise", "detailed", "dramatic".
        templates:
            Custom template overrides.
        """
```

#### Methods

##### `narrate_state`

```python
def narrate_state(self, state: VesselState) -> str:
    """Generate narrative description of current state.

        Parameters
        ----------
        state:
            VesselState instance.

        Returns
        -------
        str
            Natural language description.
    """
```

##### `narrate_action`

```python
def narrate_action(self, action: dict[str, Any]) -> str:
    """Generate narrative description of an action.

        Parameters
        ----------
        action:
            Action record from A2A log.

        Returns
        -------
        str
            Natural language description.
    """
```

---

## HTTP Endpoints

### Health Endpoints

#### `GET /health`

Overall health status with component details.

**Response Codes:**
- `200 OK` — No component failures
- `503 Service Unavailable` — At least one component failed

**Response Body:**
```json
{
  "status": "healthy",
  "vessel_id": "FV-EILEEN",
  "uptime_s": 3600.5,
  "components": {
    "websocket": {
      "status": "ok",
      "connected": true,
      "bridge_url": "ws://localhost:8000",
      "breaker": {
        "state": "CLOSED",
        "failures": 0,
        "successes": 42
      },
      "viewers": 2
    },
    "log_files": {
      "status": "ok",
      "a2a_log": {
        "status": "ok",
        "path": "logs/a2a.jsonl"
      },
      "bathymetry": {
        "status": "ok",
        "path": "data/bathymetry.json"
      }
    },
    "memory": {
      "status": "ok",
      "limit_mb": 512.0,
      "rss_mb": 420.3
    }
  }
}
```

#### `GET /ready`

Readiness probe for Kubernetes.

**Response Codes:**
- `200 OK` — Ready (connected + no failures)
- `503 Service Unavailable` — Not ready

**Response Body:**
```json
{
  "status": "ready",
  "components": {...}
}
```

#### `GET /live`

Liveness probe (always returns 200 if process is alive).

**Response Codes:**
- `200 OK` — Process is alive

**Response Body:**
```json
{
  "status": "alive",
  "uptime_s": 3600.5
}
```

### Metrics Endpoint

#### `GET /metrics`

Prometheus text format metrics scrape endpoint.

**Response:**
```
# HELP aelma_packets_received_total Telemetry packets received
# TYPE aelma_packets_received_total counter
aelma_packets_received_total 1234

# HELP aelma_websocket_connections Current viewer connections
# TYPE aelma_websocket_connections gauge
aelma_websocket_connections 2

# HELP aelma_packet_handling_seconds Packet processing time
# TYPE aelma_packet_handling_seconds histogram
aelma_packet_handling_seconds_bucket{le="0.005"} 950
aelma_packet_handling_seconds_bucket{le="0.01"} 1200
aelma_packet_handling_seconds_bucket{le="+Inf"} 1234
aelma_packet_handling_seconds_sum 2.456
aelma_packet_handling_seconds_count 1234
```

---

## WebSocket Protocol

### Viewer WebSocket (Twin → Dashboard)

**URL:** `ws://localhost:8090`

**Messages:**

#### VesselStateSnapshot

```json
{
  "type": "state",
  "timestamp": 1234567890.123,
  "vessel_id": "FV-EILEEN",
  "position": {
    "lat": 56.8013,
    "lon": -135.3028
  },
  "depth_m": 73.2,
  "speed_kn": 5.2,
  "heading_deg": 180.5,
  "sea_temp_c": 12.3,
  "wind_kts_true": 12.5,
  "wind_dir_deg_true": 45.0,
  "bathymetry": {
    "voxels": [
      {"x": 0, "y": 0, "z": 73.2, "confidence": 0.9}
    ],
    "count": 1
  }
}
```

#### Action Message

```json
{
  "type": "action",
  "action": "raise_alert",
  "payload": {
    "kind": "shallow_water",
    "depth": 1.4
  },
  "reason": "depth=1.40m",
  "priority": 0.85,
  "rule_id": "shallow-water"
}
```

---

## Data Schemas

### TelemetryPacket

```typescript
{
  timestamp: number;        // Unix timestamp (seconds)
  source: string;           // "nmea0183", "signalk", "simulator"
  readings: Reading[];
}

type Reading = {
  source: string;           // Data source
  channel: string;         // AELMA channel name
  value: number | string;  // Reading value
  path?: string;           // Source path (optional)
  quality?: string;        // "good", "fair", "poor", "bad"
};
```

### VesselStateSnapshot

```typescript
{
  type: "state";
  timestamp: number;
  vessel_id: string;
  position: {
    lat: number;
    lon: number;
  };
  depth_m?: number;
  speed_kn?: number;
  heading_deg?: number;
  sea_temp_c?: number;
  wind_kts_true?: number;
  wind_dir_deg_true?: number;
  bathymetry?: {
    voxels: Voxel[];
    count: number;
  };
}

type Voxel = {
  x: number;
  y: number;
  z: number;
  confidence: number;
};
```

### ActionRecord

```typescript
{
  kind: "action";
  action: string;
  payload: Record<string, unknown>;
  source: "watcher" | "llm" | "crew" | "system";
  reason: string;
  priority: number;        // 0.0 - 1.0
  ts: string;              // ISO 8601
  _loggedAt: string;       // ISO 8601
  _seq: number;
}
```

---

## Quick Reference

### Import Patterns

```python
# Twin core
from twin.core import TwinCore

# Watchers
from twin.watchers import WatcherRegistry, WatcherRule, ALLOWED_ACTIONS

# A2A system
from twin.a2a_log import A2ALog, KIND_ACTION, VALID_SOURCES
from twin.a2a_query import A2AQuery

# Queries
from twin.telemetry_query import TelemetryQuery
from bridge.signalk import parse_delta, SignalKDelta

# Observability
from twin.health import HealthChecker, OK, DEGRADED, FAIL
from twin.metrics import MetricsCollector, serve_metrics
from twin.circuit_breaker import CircuitBreaker, CircuitOpenError
```

### Common Patterns

```python
# Create TwinCore with all components
twin = TwinCore(
    vessel_id="FV-EILEEN",
    bridge_url="ws://localhost:8000",
    viewer_port=8090,
    health_port=8091,
    metrics_port=9090
)

# Add a watcher rule
twin.add_watcher({
    "id": "shallow-water",
    "name": "Shallow water warning",
    "when": lambda f: f.get("depth_m", 999) < 2.0,
    "action": {
        "name": "raise_alert",
        "payload": lambda f: {"kind": "shallow_water", "depth": f["depth_m"]},
        "reason": lambda f: f"depth={f['depth_m']:.2f}m",
        "priority": lambda f: 0.85,
    },
    "cooldown_s": 30.0,
})

# Query actions
actions = await twin.query_actions(
    start_ts=datetime.now() - timedelta(hours=1),
    action="raise_alert",
    min_priority=0.7
)

# Query telemetry
data = await twin.query_telemetry(
    channels=["depth_m", "speed_kn"],
    start=datetime.now() - timedelta(hours=1),
    end=datetime.now(),
    downsample_to=60
)

# Start all services
await twin.start()
```

---

**API Reference Version:** 2.0.0
**Last Updated:** 2026-07-27
**Status:** Production Ready
