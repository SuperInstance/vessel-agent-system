# A2A (Agent-to-Agent) Action Log and Query System

## Overview

The A2A system provides an append-only audit trail of all agent-to-agent actions in AELMA. It answers the question: "Who told the viewer to do what, and when?" This is the foundation for accountability, debugging, and historical analysis of agent behavior.

**Key Design Principles:**
- **Append-only**: Records are never mutated; corrections are new records
- **Single-writer**: A2ALog serializes concurrent writes
- **Streaming queries**: A2AQuery reads safely from live log files
- **Rotation support**: Size-based log rotation with configurable retention
- **Pure stdlib**: No external dependencies beyond Python standard library

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    A2A Action History                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │   A2ALog     │────────>│  a2a.jsonl   │                 │
│  │  (Write)     │         │  (Storage)    │                 │
│  └──────────────┘         └──────────────┘                 │
│         │                            │                       │
│         | writes                     | reads                 │
│         ↓                            ↓                       │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ Watchers     │         │  A2AQuery    │                 │
│  │ LLM          │         │  (Read)      │                 │
│  │ Crew         │         │              │                 │
│  └──────────────┘         └──────────────┘                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. A2ALog (twin/a2a_log.py)

**Purpose:** Append-only JSONL writer for A2A actions.

**Key Features:**
- Asyncio-safe concurrent writes
- Input validation (never writes malformed records)
- Automatic sequence numbering
- Size-based rotation
- Configurable retention

**Record Format:**
```json
{
  "kind": "action",
  "action": "raise_alert",
  "payload": {"kind": "shallow_water", "depth": 1.4},
  "source": "watcher",
  "reason": "depth=1.40m",
  "priority": 0.85,
  "ts": "2026-07-27T15:04:23.181000+00:00",
  "_loggedAt": "2026-07-27T15:04:23.204112+00:00",
  "_seq": 42
}
```

**Fields:**
- `kind`: Record type (always "action" for now)
- `action`: Action name (must be in ALLOWED_ACTIONS)
- `payload`: Action-specific data
- `source`: Origin (watcher | llm | crew | system)
- `reason`: Human-readable explanation
- `priority`: Urgency score (0.0..1.0)
- `ts`: When the action occurred
- `_loggedAt`: When it was written (metadata)
- `_seq`: Monotonic sequence number (metadata)

**Usage:**
```python
from twin.a2a_log import A2ALog

# Initialize (with optional rotation)
log = A2ALog("a2a.jsonl", max_bytes=10_000_000, keep=5)

# Log an action
record = await log.append(
    "raise_alert",
    {"kind": "shallow_water", "depth": 1.2},
    source="watcher",
    reason="depth=1.20m",
    priority=0.85,
)

# Check status
stats = await log.stats()
print(f"Records: {stats['records']}, Size: {stats['size_bytes']}")

# Close (optional but recommended)
await log.close()
```

### 2. A2AQuery (twin/a2a_query.py)

**Purpose:** Streaming read-only query layer over A2A logs.

**Key Features:**
- Filter by any field (action, source, priority, time range)
- Aggregations (count by, top N, summary, time buckets)
- Streaming generator (memory-efficient)
- Malformed line handling (counts but doesn't crash)

**Filter Format:**
```python
filters = {
    "action": "raise_alert",        # Exact match
    "source": "watcher",            # Exact match
    "since": "2026-07-27T12:00:00Z",  # ts >= since
    "until": "2026-07-27T18:00:00Z",  # ts <= until
    "min_priority": 0.7,            # priority >= min
    "max_priority": 0.9,            # priority <= max
    "reason_contains": "depth",     # Substring search
}
```

**Usage:**
```python
from twin.a2a_query import A2AQuery

query = A2AQuery("a2a.jsonl")

# Stream all records
async for record in query.iter_records():
    print(record["action"])

# Query with filters
alerts = await query.query({"action": "raise_alert"})

# Aggregations
counts = await query.count_by("source")        # {"watcher": 10, "llm": 5}
top_actions = await query.top_by("action", 5)  # Most frequent actions
summary = await query.summary()                 # Overall stats

# Recent records (newest first)
recent = await query.recent(limit=10)

# Time bucketing (e.g., actions per hour)
buckets = await query.bucket_by_time(3600)
```

### 3. TwinCore Integration (twin/core.py)

**Purpose:** Wire A2ALog into the twin runtime.

**Changes:**
- Added `a2a_log_path`, `a2a_max_bytes`, `a2a_keep` parameters
- Initialize A2ALog on startup
- Provide `log_action()` method for components

**Usage:**
```python
from twin.core import TwinCore

# Twin automatically initializes A2ALog
twin = TwinCore(
    a2a_log_path="a2a.jsonl",
    a2a_max_bytes=10_000_000,
    a2a_keep=5,
)

# Components can log actions
await twin.log_action(
    "raise_alert",
    {"kind": "shallow_water"},
    source="watcher",
    reason="depth=1.20m",
    priority=0.85,
)
```

## Integration Points

### 1. Watcher Actions

When a WatcherRegistry rule fires, log it:

```python
from twin.watchers import WatcherRegistry

registry = WatcherRegistry()
registry.on("fired", lambda rule, frame, action: asyncio.create_task(
    twin.log_action(
        action["name"],
        action["payload"](frame),
        source="watcher",
        reason=action["reason"](frame),
        priority=action["priority"](frame),
    )
))
```

### 2. LLM Narrator Actions

When the LLM narrator issues an action:

```python
from twin.llm_narrator import Narrator

narrator = Narrator()
action = await narrator.decide_action(snapshot)

await twin.log_action(
    action["name"],
    action.get("payload", {}),
    source="llm",
    reason=action.get("reason", ""),
    priority=action.get("priority", 0.5),
)
```

### 3. Manual Crew Actions

When crew manually trigger actions via viewer:

```python
# WebSocket handler for manual actions
async def handle_manual_action(ws, message):
    await twin.log_action(
        message["action"],
        message.get("payload"),
        source="crew",
        reason=message.get("reason", "Manual trigger"),
        priority=message.get("priority", 0.5),
    )
```

## Rotation

### Why Rotate?

- Prevent unbounded disk growth
- Maintain manageable log files
- Enable time-based retention policies

### How It Works

```
1. Write record → check size
2. If size + new_record > max_bytes:
   a. Delete .N file (oldest)
   b. .(N-1) → .N
   c. .(N-2) → .(N-1)
   d. ...
   e. current → .1
   f. Create new current file
3. Write record to new current file
```

### Configuration

```python
# Disable rotation (default)
log = A2ALog("a2a.jsonl")

# Enable: rotate at 10MB, keep 5 files
log = A2ALog("a2a.jsonl", max_bytes=10_000_000, keep=5)

# Result: a2a.jsonl (current) + .1, .2, .3, .4, .5 (rotated)
```

### Querying Rotated Logs

A2AQuery only reads the current log file. To query rotated files:

```python
from pathlib import Path
from twin.a2a_query import A2AQuery

base = Path("a2a.jsonl")
files = [base] + sorted(base.parent.glob("a2a.jsonl.*"))

all_records = []
for file in reversed(files):  # Oldest to newest
    query = A2AQuery(file)
    all_records.extend(await query.query())

# Now you have the full history
```

## Best Practices

### 1. Source Attribution

Always use the correct source:
- `watcher`: Deterministic threshold rules
- `llm`: Model-generated actions (Narrator, etc.)
- `crew`: Human-entered actions
- `system`: Internal bookkeeping

### 2. Priority Levels

Use priority consistently:
- `0.9-1.0`: Critical safety alerts
- `0.7-0.9`: Important mode changes
- `0.5-0.7`: Normal alerts
- `0.3-0.5`: Informational
- `0.0-0.3`: Low-priority debugging

### 3. Reason Messages

Write clear, concise reasons:
- ❌ "alert triggered"
- ✅ "depth=1.20m, transiting harbor at 5.2kn"

### 4. Payload Design

Keep payloads focused:
- Include necessary data (depth, speed, etc.)
- Omit redundant context (already in `ts`, `source`)
- Use consistent naming conventions

### 5. Query Performance

For large logs:
- Use time-bounded filters (`since`, `until`)
- Use aggregations instead of loading all records
- Consider rotating logs frequently

## Testing

Run the test suite:

```bash
# From repo root
python -m pytest tests/a2a.test.py -v

# With coverage
python -m pytest tests/a2a.test.py --cov=twin.a2a_log --cov=twin.a2a_query
```

**Test Coverage:**
- Basic append/query operations
- Validation and error handling
- Rotation logic
- Filter operations
- Aggregations
- Integration workflows

## Troubleshooting

### Append after close

```python
RuntimeError: A2ALog: append after close()
```

Don't append after closing the log. Check `log.closed` first.

### Invalid source

```python
ValueError: A2ALog.append: source must be one of ['crew', 'llm', 'system', 'watcher']
```

Use only the four valid sources.

### Priority out of range

```python
ValueError: A2ALog.append: priority 1.5 out of range [0.0, 1.0]
```

Priority must be between 0.0 and 1.0 inclusive.

### Malformed log lines

A2AQuery silently skips malformed lines but counts them:

```python
query = A2AQuery("a2a.jsonl")
await query.query()
print(f"Skipped {query.last_bad_lines} bad lines")
```

## Reference

### Constants

```python
# Default priority when not specified
DEFAULT_PRIORITY = 0.5

# Valid action sources
VALID_SOURCES = {"watcher", "llm", "crew", "system"}

# Record kind for normal actions
KIND_ACTION = "action"

# Recognized filter keys
KNOWN_FILTERS = {
    "kind", "action", "source", "since", "until",
    "min_priority", "max_priority", "reason_contains"
}
```

### A2ALog API

```python
class A2ALog:
    def __init__(self, path, max_bytes=None, keep=5):
        """Initialize log at path with optional rotation."""

    async def append(self, action, payload=None, source="system", reason="", priority=0.5, ts=None):
        """Validate and persist one action record. Returns complete record."""

    async def close(self):
        """Mark log closed. Further appends raise RuntimeError."""

    async def stats(self):
        """Return status snapshot: path, records, closed, size_bytes, max_bytes, keep."""

    async def __aenter__(self):
        """Context manager entry."""

    async def __aexit__(self, *exc):
        """Context manager exit (calls close())."""
```

### A2AQuery API

```python
class A2AQuery:
    def __init__(self, path):
        """Initialize query layer for log file at path."""

    async def iter_records(self, filters=None):
        """Yield matching records (streaming)."""

    async def query(self, filters=None, limit=0):
        """Collect matching records (limit<=0 means no limit)."""

    async def count_by(self, field, filters=None):
        """Group records by field and count each value."""

    async def top_by(self, field, n=5, filters=None):
        """Return top-N most frequent field values."""

    async def by_source(self, source, filters=None, limit=0):
        """Convenience: query with source filter."""

    async def summary(self, filters=None):
        """Return aggregated summary (total, breakdowns, time span, avg_priority)."""

    async def bucket_by_time(self, bucket_s, filters=None):
        """Group records into fixed-width time buckets."""

    async def recent(self, limit=10, filters=None):
        """Return most recent N records in reverse chronological order."""
```

## Migration from mini-agent

This is a Python/asyncio adaptation of the mini-agent's `backend/a2aLog.js` and `backend/a2aQuery.js`. Key differences:

1. **Asyncio vs callbacks**: Uses `async/await` instead of promises
2. **Rotating files**: Python version has built-in rotation (JS was manual)
3. **Pure stdlib**: No external dependencies (mini-agent used some packages)
4. **Type hints**: Full type annotations for better IDE support

Contract compatibility:
- ✅ Append-only records
- ✅ Input validation
- ✅ Monotonic sequences
- ✅ Filter operations
- ✅ Aggregations
- ✅ Malformed line handling

## Future Enhancements

Potential improvements for future iterations:

1. **Compression**: Compress rotated logs (.1.gz, .2.gz)
2. **Indexing**: Build lightweight index for faster queries
3. **Replication**: Stream records to remote storage
4. **Schema evolution**: Support multiple record versions
5. **Query API**: REST endpoint for web UI queries

## Related Documentation

- [Watcher Registry Guide](watcher_registry_guide.md)
- [LLM Narrator System](../llm_narrator.md)
- [TwinCore Architecture](../ARCHITECTURE.md)

---

**Last Updated:** 2026-07-27
**Status:** Production Ready
**Dependencies:** Python 3.11+, asyncio (stdlib only)
