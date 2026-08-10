# bridge/ — NMEA and Signal K Bridge

> *The translator between salt and silicon.*

The bridge is the first component to touch raw marine data. It parses NMEA 0183 sentences from TCP or serial sources, quality-checks each sentence, and produces TelemetryPackets for the twin core.

## Files

| File | Description |
|------|-------------|
| [`bridge.py`](bridge.py) | **NMEABridge** and **SignalKBridge** — TCP/serial ingestion, parsing, packet generation. |
| [`nmea.py`](nmea.py) | NMEA 0183 sentence parser. GGA, RMC, GLL, DBT, DBS, MTW, MWV, and more. |
| [`signalk.py`](signalk.py) | Signal K delta parser. Modern marine data format. |
| [`quality.py`](quality.py) | Quality checks: checksum validation, stale data detection, spike filtering. |

## How It Works

```
$GPGGA,092750.000,5321.6802,N,00606.7032,W,1,8,1.03,61.7,M,55.2,M,,*76
       │           │            │             │
       └─── parse ──┴── quality ─┴── validate ─┘
                                      │
                                      ▼
                             TelemetryPacket
                             {channel, value, timestamp_ns, source}
```

The bridge is the Level 0 boundary: everything above it trusts that packets are parsed correctly and quality-checked.

See the [Architecture document](../docs/ARCHITECTURE.md) for the full bridge design.

---

[← Back to AELMA](../README.md) | [← Vessel Agent System](../../README.md)
