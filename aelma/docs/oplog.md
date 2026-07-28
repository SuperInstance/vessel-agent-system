# OpLog: Vessel Operations Log

## Overview

OpLog provides an append-only audit trail of manual crew operations in AELMA. It complements the automated A2A action log by tracking crew-initiated activities such as gear deployment, haul operations, catch logging, anchor handling, manual alerts, and general crew notes.

**Key Design Principles:**
- **Append-only**: Records are never mutated; corrections are new records
- **Crew-centric**: All entries identify the crew member responsible
- **Structured metadata**: Rich, queryable data alongside human-readable messages
- **Rotation support**: Size-based log rotation with configurable retention
- **Export flexibility**: JSON, CSV, and text export formats
- **Pure stdlib**: No external dependencies beyond Python standard library

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpLog System                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │   OpLog      │────────>│ oplog.jsonl  │                 │
│  │  (Write)     │         │  (Storage)   │                 │
│  └──────────────┘         └──────────────┘                 │
│         │                            │                       │
│         | writes                     | reads                 │
│         ↓                            ↓                       │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ TwinCore     │         │  OpLog       │                 │
│  │ Viewers      │         │  query()     │                 │
│  │ Crew UI      │         │  export()    │                 │
│  └──────────────┘         └──────────────┘                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Entry Types

OpLog supports nine predefined entry types covering common vessel operations:

| Entry Type | Description | Typical Metadata |
|------------|-------------|------------------|
| `gear_deployed` | Fishing gear deployed | gear_type, count, lat, lon, depth |
| `gear_retrieved` | Fishing gear retrieved from water | gear_type, total_count, duration |
| `haul_started` | Fishing haul commenced | gear_type, location, method |
| `haul_complete` | Fishing haul completed | gear_type, catch_estimate, duration |
| `anchor_drop` | Vessel anchor deployed | depth_ft, scope_ratio, location |
| `anchor_raise` | Vessel anchor retrieved | duration_min, condition |
| `manual_alert` | Crew-initiated alert | alert_type, severity, description |
| `crew_note` | General crew observation | subject, conditions, notes |
| `catch_logged` | Species/catch data recorded | species, weight_lb, count, grade |

## Components

### 1. OpLog (twin/oplog.py)

**Purpose:** Append-only JSONL writer for crew operations.

**Key Features:**
- Asyncio-safe concurrent writes
- Input validation (never writes malformed records)
- Automatic sequence numbering
- Size-based rotation
- Configurable retention
- Query with filters
- Export to JSON/CSV/text

**Record Format:**

```json
{
  "kind": "oplog_entry",
  "entry_type": "gear_deployed",
  "crew": "captain",
  "message": "Deployed cod pot gear at 59.5N, -152.3W",
  "metadata": {
    "gear_type": "cod_pot",
    "count": 50,
    "lat": 59.5,
    "lon": -152.3,
    "depth_m": 45
  },
  "ts": "2026-07-28T10:30:00.000000+00:00",
  "_loggedAt": "2026-07-28T10:30:00.123456+00:00",
  "_seq": 42
}
```

**Fields:**
- `kind`: Record type identifier (always "oplog_entry")
- `entry_type`: One of the nine predefined operation types
- `crew`: Crew member identifier (name, ID, or role)
- `message`: Human-readable description of the operation
- `metadata`: Optional structured data (gear specs, quantities, locations, etc.)
- `ts`: When the operation occurred (ISO 8601 timestamp)
- `_loggedAt`: When the record was written (ISO 8601 timestamp)
- `_seq`: Monotonically increasing sequence number

**Core Methods:**

```python
async def log_entry(
    entry_type: str,
    crew: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    *,
    ts: Any = None,
) -> dict[str, Any]
```

Log a crew operation entry.

**Parameters:**
- `entry_type`: Type of operation (gear_deployed, haul_started, etc.)
- `crew`: Crew member identifier
- `message`: Human-readable description
- `metadata`: Optional structured data
- `ts`: Timestamp (None for now, datetime, epoch seconds, or ISO string)

**Returns:** The logged record as written to disk

**Example:**

```python
await oplog.log_entry(
    "gear_deployed",
    "captain",
    "Deployed cod pot gear at 59.5N, -152.3W",
    {"gear_type": "cod_pot", "count": 50, "lat": 59.5, "lon": -152.3}
)
```

---

```python
async def query(
    *,
    entry_type: str | set[str] | None = None,
    crew: str | set[str] | None = None,
    start_time: Any = None,
    end_time: Any = None,
    limit: int = 1000,
    offset: int = 0,
) -> list[dict[str, Any]]
```

Query operations log with filters.

**Parameters:**
- `entry_type`: Filter by entry type (string or set). None = all types
- `crew`: Filter by crew member (string or set). None = all crew
- `start_time`: Filter entries after this time (datetime, epoch seconds, or ISO string)
- `end_time`: Filter entries before this time (datetime, epoch seconds, or ISO string)
- `limit`: Maximum number of entries to return (default 1000)
- `offset`: Number of entries to skip for pagination (default 0)

**Returns:** List of matching records, sorted by timestamp (newest first)

**Examples:**

```python
# All gear deployment entries
gear_ops = await oplog.query(entry_type="gear_deployed")

# Captain's haul operations today
captain_hauls = await oplog.query(
    entry_type={"haul_started", "haul_complete"},
    crew="captain",
    start_time=datetime.now(timezone.utc) - timedelta(days=1)
)

# Last 10 manual alerts
recent_alerts = await oplog.query(
    entry_type="manual_alert",
    limit=10
)
```

---

```python
async def export(
    format: str = "json",
    *,
    entry_type: str | set[str] | None = None,
    crew: str | set[str] | None = None,
    start_time: Any = None,
    end_time: Any = None,
    limit: int = 1000,
) -> str
```

Export operations log to specified format.

**Parameters:**
- `format`: Export format: 'json', 'csv', or 'text' (default 'json')
- `entry_type`, `crew`, `start_time`, `end_time`, `limit`: Same filters as query()

**Returns:** Exported data in requested format

**Examples:**

```python
# Export to JSON
json_data = await oplog.export(format="json", crew="captain")

# Export to CSV
csv_data = await oplog.export(
    format="csv",
    entry_type="catch_logged",
    start_time="2026-07-01T00:00:00+00:00"
)

# Export human-readable text report
text_report = await oplog.export(
    format="text",
    entry_type={"gear_deployed", "haul_complete", "catch_logged"}
)
```

### 2. TwinCore Integration (twin/core.py)

**Purpose:** Expose OpLog functionality through the main twin interface.

**New Constructor Parameters:**

```python
TwinCore(
    ...
    oplog_path: str | Path = "oplog.jsonl",
    oplog_max_bytes: int | None = None,
    oplog_keep: int = 5,
    ...
)
```

**Parameters:**
- `oplog_path`: Path to the oplog JSONL file (default "oplog.jsonl")
- `oplog_max_bytes`: Rotate log files after this size (default None, disabled)
- `oplog_keep`: Number of rotated files to keep (default 5)

**New Methods:**

```python
async def log_crew_action(
    entry_type: str,
    crew: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    *,
    ts: Any = None,
) -> dict[str, Any]
```

Log a crew operations entry. This is the main entry point for logging manual crew operations.

**Example:**

```python
await twin.log_crew_action(
    "catch_logged",
    "captain",
    "Caught 500lb pollock, good quality",
    {"species": "pollock", "weight_lb": 500, "grade": "A"}
)
```

---

```python
async def query_oplog(
    *,
    entry_type: str | set[str] | None = None,
    crew: str | set[str] | None = None,
    start_time: Any = None,
    end_time: Any = None,
    limit: int = 1000,
    offset: int = 0,
) -> list[dict[str, Any]]
```

Query the operations log with filters.

---

```python
async def export_oplog(
    format: str = "json",
    *,
    entry_type: str | set[str] | None = None,
    crew: str | set[str] | None = None,
    start_time: Any = None,
    end_time: Any = None,
    limit: int = 1000,
) -> str
```

Export the operations log to specified format.

## Usage Examples

### Complete Fishing Operation

```python
import asyncio
from datetime import datetime, timezone, timedelta
from twin.core import TwinCore

async def track_fishing_operation():
    twin = TwinCore()

    # Deploy gear
    await twin.log_crew_action(
        "gear_deployed",
        "captain",
        "Deployed cod pot gear at 59.5N, -152.3W",
        {
            "gear_type": "cod_pot",
            "count": 50,
            "lat": 59.5,
            "lon": -152.3,
            "depth_m": 45
        },
        ts=datetime(2026, 7, 28, 6, 0, 0, tzinfo=timezone.utc)
    )

    # Start hauling
    await twin.log_crew_action(
        "haul_started",
        "crewman",
        "Started hauling pot string 1",
        {"string_number": 1, "pot_count": 25},
        ts=datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc)
    )

    # Complete haul
    await twin.log_crew_action(
        "haul_complete",
        "captain",
        "Completed haul of string 1, good catch",
        {
            "string_number": 1,
            "total_pots": 25,
            "duration_minutes": 30,
            "estimated_catch_lb": 1200
        }
    )

    # Log catch
    await twin.log_crew_action(
        "catch_logged",
        "captain",
        "Logged catch: cod, 1200lb, grade A",
        {"species": "cod", "weight_lb": 1200, "grade": "A"}
    )

    # Query the complete operation
    operation = await twin.query_oplog(
        entry_type={"gear_deployed", "haul_started", "haul_complete", "catch_logged"},
        crew="captain",
        limit=10
    )

    print(f"Operation has {len(operation)} entries")
    for entry in operation:
        print(f"[{entry['ts']}] {entry['entry_type']}: {entry['message']}")

asyncio.run(track_fishing_operation())
```

### Crew Shift Tracking

```python
async def track_crew_shift():
    twin = TwinCore()

    # Morning shift handoff
    await twin.log_crew_action(
        "crew_note",
        "captain_john",
        "Shift started, weather good, all systems green",
        {"wind_kts": 10, "visibility": "good", "sea_state": "2"}
    )

    # Mid-shift alert
    await twin.log_crew_action(
        "manual_alert",
        "crewman_steve",
        "Noticed slight oil leak in winch, monitoring",
        {"alert_type": "maintenance", "severity": "low", "location": "winch"}
    )

    # Shift change
    await twin.log_crew_action(
        "crew_note",
        "captain_jane",
        "Shift change: relieved John, noted winch issue",
        {"outgoing_captain": "john", "incoming_captain": "jane"}
    )

    # Query John's shift
    john_shift = await twin.query_oplog(
        crew="captain_john",
        limit=50
    )

    print(f"Captain John logged {len(john_shift)} entries this shift")

asyncio.run(track_crew_shift())
```

### Generating Reports

```python
async def generate_fishing_report():
    twin = TwinCore()

    # Today's catch report (JSON)
    json_report = await twin.export_oplog(
        format="json",
        entry_type="catch_logged",
        start_time=datetime.now(timezone.utc) - timedelta(days=1)
    )

    # Weekly operations summary (CSV)
    csv_report = await twin.export_oplog(
        format="csv",
        start_time=datetime.now(timezone.utc) - timedelta(days=7),
        limit=500
    )

    # Human-readable captain's log (text)
    text_report = await twin.export_oplog(
        format="text",
        crew="captain",
        start_time=datetime.now(timezone.utc) - timedelta(days=7),
        limit=100
    )

    print("=== Captain's Log (Last 7 Days) ===")
    print(text_report)

asyncio.run(generate_fishing_report())
```

### Anchor Operations

```python
async def track_anchor_ops():
    twin = TwinCore()

    # Drop anchor
    await twin.log_crew_action(
        "anchor_drop",
        "captain",
        "Dropped anchor in 40ft, 7:1 scope",
        {"depth_ft": 40, "scope_ratio": 7, "location": "protected_cove"}
    )

    # Later, raise anchor
    await twin.log_crew_action(
        "anchor_raise",
        "captain",
        "Raised anchor after 8 hours, chain in good condition",
        {"duration_min": 480, "condition": "good"}
    )

    # Query anchor operations
    anchor_ops = await twin.query_oplog(
        entry_type={"anchor_drop", "anchor_raise"},
        limit=20
    )

    print(f"Found {len(anchor_ops)} anchor operations")

asyncio.run(track_anchor_ops())
```

## Storage and Rotation

### File Format

OpLog uses JSONL (JSON Lines) format:
- One JSON object per line
- Append-only writes
- Newlines separate records
- Easy to parse with standard tools

### Rotation Strategy

When `oplog_max_bytes` is set:

1. Current file size is checked before each write
2. If writing the next line would exceed max_bytes:
   - Current file is renamed to `oplog.jsonl.1`
   - Existing `oplog.jsonl.1` → `oplog.jsonl.2`
   - Existing `oplog.jsonl.2` → `oplog.jsonl.3`
   - ...
   - Oldest rotated file (oplog.jsonl.N) is deleted
3. New entries are written to fresh `oplog.jsonl`

**Example with max_bytes=1MB, keep=3:**

```
After rotation:
├── oplog.jsonl        (new, empty)
├── oplog.jsonl.1      (most recent, ~1MB)
├── oplog.jsonl.2      (older, ~1MB)
└── oplog.jsonl.3      (oldest, ~1MB)

(oplog.jsonl.4 would be deleted)
```

### Query Across Rotated Files

The `query()` method automatically reads from:
1. Active file (oplog.jsonl)
2. All rotated files (oplog.jsonl.1, .2, .3, ...)

Results are merged, sorted by timestamp, and filtered/paginated.

## Export Formats

### JSON Export

```json
[
  {
    "kind": "oplog_entry",
    "entry_type": "catch_logged",
    "crew": "captain",
    "message": "Caught 500lb pollock",
    "metadata": {"species": "pollock", "weight_lb": 500},
    "ts": "2026-07-28T14:30:00+00:00",
    "_loggedAt": "2026-07-28T14:30:05.123456+00:00",
    "_seq": 42
  }
]
```

### CSV Export

```csv
crew,_loggedAt,_seq,entry_type,kind,message,metadata_species,metadata_weight_lb,ts
captain,2026-07-28T14:30:05.123456+00:00,42,catch_logged,oplog_entry,"Caught 500lb pollock",pollock,500,2026-07-28T14:30:00+00:00
```

Note: Metadata fields are flattened with `metadata_` prefix.

### Text Export

```
[2026-07-28T14:30:00+00:00] catch_logged - captain
  Caught 500lb pollock
  species: pollock
  weight_lb: 500

[2026-07-28T13:45:00+00:00] gear_deployed - captain
  Deployed trawl gear
  gear_type: trawl
  depth_m: 100
```

## API Reference

### OpLog Constructor

```python
OpLog(
    path: str | Path,
    *,
    max_bytes: int | None = None,
    keep: int = 5,
)
```

**Parameters:**
- `path`: Destination JSONL file. Parent directories created on first append.
- `max_bytes`: Rotate log files after this size. Disabled (None) by default.
- `keep`: Number of rotated files to keep when max_bytes set. Must be at least 1.

### OpLog Methods

#### log_entry

```python
async def log_entry(
    entry_type: str,
    crew: str,
    message: str,
    metadata: Mapping[str, Any] | None = None,
    *,
    ts: Any = None,
) -> dict[str, Any]
```

**Raises:**
- `ValueError`: Invalid entry_type, empty crew/message
- `TypeError`: Invalid metadata type
- `RuntimeError`: log_entry after close()

#### query

```python
async def query(
    *,
    entry_type: str | set[str] | None = None,
    crew: str | set[str] | None = None,
    start_time: Any = None,
    end_time: Any = None,
    limit: int = 1000,
    offset: int = 0,
) -> list[dict[str, Any]]
```

**Returns:** Records sorted by timestamp descending (newest first)

#### export

```python
async def export(
    format: str = "json",
    *,
    entry_type: str | set[str] | None = None,
    crew: str | set[str] | None = None,
    start_time: Any = None,
    end_time: Any = None,
    limit: int = 1000,
) -> str
```

**Raises:**
- `ValueError`: Invalid format (must be 'json', 'csv', or 'text')

#### stats

```python
async def stats() -> dict[str, Any]
```

**Returns:** Dictionary with path, records, closed, size_bytes, max_bytes, keep

#### close

```python
async def close() -> None
```

Mark the log closed. Later operations raise RuntimeError.

## Validation Rules

### Entry Types

Must be one of:
- `gear_deployed`
- `gear_retrieved`
- `haul_started`
- `haul_complete`
- `anchor_drop`
- `anchor_raise`
- `manual_alert`
- `crew_note`
- `catch_logged`

### Crew

- Must be a non-empty string
- Whitespace is trimmed
- No length limit (practical limit: 100 chars)

### Message

- Must be a non-empty string
- Whitespace is trimmed
- No length limit (practical limit: 1000 chars)

### Metadata

- Must be a mapping (dict) or None
- Keys must be strings
- Values can be any JSON-serializable type
- Flattened in CSV export with `metadata_` prefix

### Timestamps

Accepted formats:
- `None`: Current UTC time
- `datetime`: Naive assumed UTC, aware used as-is
- `int/float`: Epoch seconds
- `str`: ISO 8601 string (validated by round-trip)

## Best Practices

### 1. Use Descriptive Messages

Bad:
```python
await twin.log_crew_action("catch_logged", "captain", "Fish")
```

Good:
```python
await twin.log_crew_action(
    "catch_logged",
    "captain",
    "Caught 500lb pollock, grade A, excellent condition",
    {"species": "pollock", "weight_lb": 500, "grade": "A", "condition": "excellent"}
)
```

### 2. Structure Metadata for Queries

Include structured data that you'll want to filter or aggregate later:

```python
# Good for later analysis
await twin.log_crew_action(
    "catch_logged",
    "captain",
    "Caught 500lb pollock",
    {
        "species": "pollock",           # For filtering by species
        "weight_lb": 500,               # For aggregation
        "grade": "A",                    # For quality filtering
        "location_lat": 59.5,           # For location analysis
        "location_lon": -152.3,
        "gear_type": "trawl",           # For gear performance
        "haul_number": 3                # For operation linking
    }
)
```

### 3. Link Related Operations

Use metadata to link related entries:

```python
haul_id = "haul_2026_07_28_001"

await twin.log_crew_action(
    "haul_started",
    "captain",
    "Started haul for pot string 1",
    {"haul_id": haul_id, "string_number": 1}
)

await twin.log_crew_action(
    "haul_complete",
    "captain",
    "Completed haul, caught 1200lb",
    {"haul_id": haul_id, "catch_lb": 1200}
)

# Query all operations for this haul
haul_ops = await twin.query_oplog(
    limit=100
)
haul_ops = [op for op in haul_ops if op.get("metadata", {}).get("haul_id") == haul_id]
```

### 4. Use Consistent Crew Identifiers

Establish a convention for crew identifiers:

```python
# By role
await twin.log_crew_action("crew_note", "captain", "Weather good")

# By name
await twin.log_crew_action("crew_note", "captain_john_smith", "Weather good")

# By ID
await twin.log_crew_action("crew_note", "CREW_001", "Weather good")
```

### 5. Export Regularly

Set up periodic exports for backup and analysis:

```python
async def daily_report():
    twin = TwinCore()

    # Export yesterday's operations
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    start_of_yesterday = yesterday.replace(hour=0, minute=0, second=0)

    # JSON for backup
    json_backup = await twin.export_oplog(
        format="json",
        start_time=start_of_yesterday,
        end_time=yesterday
    )

    # CSV for analysis
    csv_report = await twin.export_oplog(
        format="csv",
        start_time=start_of_yesterday,
        end_time=yesterday
    )

    # Text for captain's review
    text_report = await twin.export_oplog(
        format="text",
        start_time=start_of_yesterday,
        end_time=yesterday
    )

    # Save to files
    with open(f"oplog_backup_{yesterday.date()}.json", "w") as f:
        f.write(json_backup)

    with open(f"oplog_report_{yesterday.date()}.csv", "w") as f:
        f.write(csv_report)

    print(f"Generated reports for {yesterday.date()}")

asyncio.run(daily_report())
```

## Comparison: A2A Log vs OpLog

| Feature | A2A Log | OpLog |
|---------|---------|-------|
| **Purpose** | Automated agent actions | Manual crew operations |
| **Primary Source** | Watchers, LLM, system | Crew UI, manual input |
| **Entry Types** | Action names (any string) | 9 predefined types |
| **Crew Tracking** | Optional `source` field | Required `crew` field |
| **Message** | Optional `reason` | Required `message` |
| **Metadata** | `payload` (any structure) | `metadata` (any structure) |
| **Priority** | 0.0-1.0 (required) | Not applicable |
| **Use Cases** | Alerts, mode changes, automation | Gear ops, catch logging, notes |

## Testing

Comprehensive test suite in `tests/oplog.test.py`:

```bash
# Run all oplog tests
python -m pytest tests/oplog.test.py -v

# Run specific test class
python -m pytest tests/oplog.test.py::TestOpLogBasic -v

# Run with coverage
python -m pytest tests/oplog.test.py --cov=twin.oplog --cov-report=html
```

Test coverage includes:
- Basic operations (log_entry, stats, seq monotonicity)
- Validation (entry types, crew, message, metadata)
- Timestamp handling (all formats)
- Query filters (type, crew, time range, pagination)
- Export formats (JSON, CSV, text)
- Rotation (size-based, keep parameter)
- Error handling (close, invalid input)
- Integration (complete workflows)

## Performance Considerations

### Write Performance

- Each `log_entry()` is a single file append
- Asyncio lock ensures serialized writes
- Flush after each write for durability
- Typical latency: <1ms per entry

### Query Performance

- Linear scan of all log files (active + rotated)
- Filters applied during scan (early termination)
- Results sorted after collection
- For large logs, consider:
  - Using rotation to limit file sizes
  - Adding time range filters
  - Using appropriate `limit` values

### Storage Efficiency

- JSONL format: ~300 bytes per entry (typical)
- 1MB ≈ 3,300 entries
- With max_bytes=10MB: ~33,000 entries per file
- Rotation keeps disk usage bounded

## Troubleshooting

### Common Issues

**1. "Invalid entry_type" error**

```python
# Wrong
await twin.log_crew_action("gear_deploy", "captain", "Test")  # Missing 'ed'

# Right
await twin.log_crew_action("gear_deployed", "captain", "Test")
```

**2. Query returns no results**

```python
# Check your timestamp filters
from datetime import datetime, timezone

# Wrong (naive datetime)
results = await twin.query_oplog(start_time=datetime(2026, 7, 28, 10, 0))

# Right (UTC datetime)
results = await twin.query_oplog(start_time=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc))
```

**3. CSV export missing metadata fields**

```python
# Metadata fields are flattened with prefix
# Use: metadata_field_name in filters
csv = await twin.export_oplog(format="csv")
# Contains: metadata_species, metadata_weight_lb, etc.
```

## Future Enhancements

Potential additions to OpLog:

1. **Geospatial queries**: Filter by location radius
2. **Aggregation functions**: Sum catches by species, count operations by type
3. **Time series analysis**: Gear deployment patterns, haul duration trends
4. **Crew productivity**: Activity metrics by crew member
5. **Integration with A2A log**: Correlate manual ops with automated actions
6. **Web UI**: Viewer component for oplog browsing and export

## Related Documentation

- [A2A System](docs/a2a_system.md) - Automated agent-to-agent action logging
- [Architecture](docs/ARCHITECTURE.md) - Overall system architecture
- [Deployment](docs/deployment.md) - Running AELMA in production
- [Phase 2 API Reference](PHASE2_API_REFERENCE.md) - Complete API documentation
