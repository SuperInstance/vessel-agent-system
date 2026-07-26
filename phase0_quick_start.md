# Vessel Agent Phase 0 Implementation Plan - Quick Start Guide

**Deployment Target:** F/V EILEEN (51' Commercial Fishing Vessel)
**Timeline:** Days 1-30 (July - August 2026)
**Status:** Production Ready - Deploy Immediately

---

## 30-Minute Quick Start

### Step 1: Install Dependencies (5 minutes)

```bash
# Create project directory
mkdir C:\data\vessel_agent
cd C:\data\vessel_agent

# Create Python virtual environment
python -m venv venv
venv\Scripts\activate

# Install core dependencies
pip install pypcap dpkt pyarrow psutil pyserial pandas
pip install pytest pytest-asyncio
```

### Step 2: Create Directory Structure (2 minutes)

```bash
# Create archive directory
mkdir C:\data\vessel_agent\archive

# Create code directories
mkdir vessel_agent\capture
mkdir vessel_agent\storage
mkdir vessel_agent\monitoring
mkdir vessel_agent\tzpro
mkdir tests
```

### Step 3: Deploy Core Modules (20 minutes)

Copy the following Python files from `phase0_implementation_plan.md`:

1. **vessel_agent\capture\network_capture.py** - Network packet capture
2. **vessel_agent\capture\nmea_interpolator.py** - NMEA interpolation
3. **vessel_agent\storage\parquet_pipeline.py** - Parquet storage
4. **vessel_agent\monitoring\data_quality.py** - Quality monitoring
5. **vessel_agent\tzpro\lifecycle_manager.py** - TZ Pro integration
6. **capture_daemon.py** - Main daemon entry point

### Step 4: Configure System (3 minutes)

```bash
# Edit configuration
notepad vessel_agent\config.py
```

```python
# Configuration for F/V EILEEN
CONFIG = {
    # Network interface for Furuno capture
    'network_interface': 'Ethernet',  # Check with ipconfig

    # Furuno UDP port
    'furuno_port': 8000,

    # NMEA serial port
    'nmea_port': 'COM3',  # Check Windows Device Manager
    'nmea_baudrate': 4800,

    # Storage location
    'archive_path': 'C:\\data\\vessel_agent\\archive',

    # Data retention (days)
    'retention_days': 365,

    # TimeZero process name
    'tz_process_name': 'TimeZero.exe',

    # Vessel metadata
    'vessel_uuid': 'US-AK-FVEILEEN-01',
    'vessel_name': 'F/V EILEEN',
    'transducer_depth_m': 2.4,
}
```

### Step 5: Test Capture (5 minutes)

```bash
# Test network capture (10 second sample)
python capture_daemon.py test --duration 10

# Verify packet loss < 0.1%
python capture_daemon.py metrics

# Test NMEA parsing
python -m vessel_agent.capture.nmea_interpolator --test

# Test storage write
python -m vessel_agent.storage.parquet_pipeline --test
```

### Step 6: Run Production (Start Now)

```bash
# Start capture daemon
python capture_daemon.py run

# In another terminal, monitor status
python capture_daemon.py status

# Check data quality
python capture_daemon.py doctor
```

---

## Week 1 Critical Tasks (Days 1-7)

### Day 1: Network Capture Setup

**Objective:** Lossless UDP packet capture from Furuno sounder

**Tasks:**
1. Identify network interface connected to Furuno
2. Configure BPF filter for UDP port 8000
3. Test ring buffer performance
4. Verify zero-copy packet parsing

**Success Criteria:**
- 10,000+ packets/second sustained
- Packet loss < 0.1%
- Furuno header extraction working

**Command:**
```bash
python -m vessel_agent.capture.network_capture --test
```

### Day 2: NMEA Capture Setup

**Objective:** Capture GPS sentences from serial port

**Tasks:**
1. Identify NMEA serial port (COM3)
2. Test GPGGA and GPRMC parsing
3. Verify sentence validation
4. Check GPS quality indicators

**Success Criteria:**
- GPGGA/GPRMC sentences captured
- Latitude/longitude parsing correct
- GPS quality indicator working
- Satellite count tracking

**Command:**
```bash
python -m vessel_agent.capture.nmea_interpolator --test
```

### Day 3: GPS/Sounder Fusion

**Objective:** Sub-second interpolation for accurate anchoring

**Tasks:**
1. Implement dead reckoning for gaps
2. Test interpolation accuracy
3. Verify position error < 5m
4. Test vector clock synchronization

**Success Criteria:**
- Position error < 5m at 10 knots
- Dead reckoning working for 5s gaps
- Sub-second timestamps accurate

**Command:**
```bash
python -m vessel_agent.capture.nmea_interpolator --interpolation-test
```

### Day 4-7: Integration Testing

**Objective:** Full pipeline integration

**Tasks:**
1. Run 24-hour continuous capture test
2. Verify end-to-end data flow
3. Monitor system performance
4. Generate quality report

**Success Criteria:**
- 24-hour uptime
- Zero packet loss
- Position error < 5m
- CPU < 50%, Memory < 4GB

**Command:**
```bash
python capture_daemon.py run --duration 86400
```

---

## Week 2 Critical Tasks (Days 8-14)

### Day 8-10: Parquet Storage Implementation

**Objective:** High-performance columnar storage

**Tasks:**
1. Define Apache Arrow schema
2. Implement Hive partitioning
3. Test write throughput
4. Verify ICES alignment

**Success Criteria:**
- 1M+ pings/hour write throughput
- Hive partitioning working
- ICES SONAR-netCDF4 alignment verified
- Compression ratio > 5:1

**Command:**
```bash
python -m vessel_agent.storage.parquet_pipeline --benchmark
```

### Day 11-12: Data Quality Monitoring

**Objective:** Real-time quality checks and alerting

**Tasks:**
1. Implement quality checks (GPS quality, satellite count, HDOP)
2. Add alerting for data quality issues
3. Create daily health reports
4. Test auto-purge system

**Success Criteria:**
- Real-time quality checks < 1ms
- Alerting working for quality issues
- Daily health reports generating
- Auto-purge working correctly

**Command:**
```bash
python -m vessel_agent.monitoring.data_quality --test
```

### Day 13-14: Production Validation

**Objective:** Production-ready validation

**Tasks:**
1. Run 48-hour soak test
2. Monitor system metrics
3. Validate data quality
4. Generate health report

**Success Criteria:**
- 48-hour uptime
- Packet loss < 0.1%
- Position error < 5m
- Daily health report generated

**Command:**
```bash
python capture_daemon.py run --duration 172800
```

---

## Week 3-4 Critical Tasks (Days 15-30)

### Day 15-21: TZ Pro Integration

**Objective:** Non-disruptive background operation

**Tasks:**
1. Implement TimeZero process detection
2. Add auto-start/stop with TZ Pro
3. Implement CPU/memory throttling
4. Test non-disruptive operation

**Success Criteria:**
- Auto-start with TimeZero working
- Auto-stop when TimeZero closes
- CPU < 50%, Memory < 4GB
- No impact on TimeZero performance

**Command:**
```bash
python -m vessel_agent.tzpro.lifecycle_manager --test
```

### Day 22-30: Production Deployment

**Objective:** Full production deployment

**Tasks:**
1. Deploy on F/V EILEEN
2. Configure Windows service
3. Monitor daily health reports
4. Optimize based on field data

**Success Criteria:**
- 99%+ uptime during operations
- Daily health reports showing 90%+ quality
- Storage throughput > 1000 pings/sec
- Zero impact on TimeZero

**Command:**
```bash
python capture_daemon.py run --production
```

---

## File Structure (Complete)

```
C:\data\vessel_agent\
├── archive\                          # Parquet data storage
│   └── year=2026\
│       └── month=07\
│           └── day=24\
│               └── acoustic_*.parquet
├── vessel_agent\
│   ├── __init__.py
│   ├── config.py                     # Configuration file
│   ├── capture\
│   │   ├── __init__.py
│   │   ├── network_capture.py        # Week 1: BPF capture
│   │   ├── nmea_interpolator.py      # Week 1: GPS interpolation
│   │   └── capture_daemon.py         # Main daemon
│   ├── storage\
│   │   ├── __init__.py
│   │   ├── parquet_pipeline.py       # Week 2: Storage
│   │   └── schema.py                 # ICES schemas
│   ├── monitoring\
│   │   ├── __init__.py
│   │   ├── data_quality.py           # Week 2: Quality
│   │   └── health_report.py          # Daily reports
│   └── tzpro\
│       ├── __init__.py
│       ├── lifecycle_manager.py      # Week 3: TZ Pro
│       └── non_disruptive.py         # Throttling
├── tests\
│   ├── __init__.py
│   ├── test_network_capture.py
│   ├── test_nmea_interpolation.py
│   ├── test_parquet_storage.py
│   └── test_integration.py
├── requirements.txt                  # Dependencies
├── capture_daemon.py                 # Entry point
└── README.md                          # This file
```

---

## Key Commands Reference

### System Operations

```bash
# Start capture daemon
python capture_daemon.py run

# Stop capture daemon
python capture_daemon.py stop

# Check system status
python capture_daemon.py status

# Run diagnostics
python capture_daemon.py doctor

# Single capture test
python capture_daemon.py test --duration 60

# Run with TimeZero integration
python capture_daemon.py run --tz-integration
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_network_capture.py -v

# Run integration tests
pytest tests/test_integration.py -v -s

# Run with coverage
pytest tests/ --cov=vessel_agent --cov-report=html
```

### Data Queries

```python
import pyarrow.parquet as pq
import pandas as pd

# Read single day
df = pd.read_parquet('archive/year=2026/month=07/day=24/*.parquet')

# Query specific time range
df = df[(df['timestamp_ns'] >= start) & (df['timestamp_ns'] <= end)]

# Get quality summary
quality_percent = (df['quality_flag'] >= 2).sum() / len(df) * 100
```

---

## Troubleshooting

### Network Capture Issues

**Problem:** Packet loss > 0.1%
**Solution:**
- Check ring buffer capacity (increase to 1,000,000)
- Verify BPF filter is correct
- Check network interface is not overloaded

**Problem:** No packets captured
**Solution:**
- Verify network interface name with `ipconfig`
- Check Furuno is sending data on port 8000
- Test with Wireshark to verify packets exist

### NMEA Interpolation Issues

**Problem:** No GPS data
**Solution:**
- Verify serial port with Windows Device Manager
- Check baud rate (usually 4800)
- Test with serial terminal (PuTTY)

**Problem:** Position errors > 5m
**Solution:**
- Check GPS quality indicator (should be >= 2)
- Verify satellite count >= 6
- Check HDOP < 2.0

### Storage Issues

**Problem:** Slow write performance
**Solution:**
- Use SSD for archive directory
- Increase batch size to 50,000
- Use Snappy compression (default)

**Problem:** Disk filling up
**Solution:**
- Reduce retention_days in config
- Enable auto-purge
- Add additional storage

### System Performance

**Problem:** CPU > 50%
**Solution:**
- Enable throttling in non_disruptive.py
- Reduce ring buffer size
- Optimize packet parsing

**Problem:** Memory > 4GB
**Solution:**
- Reduce batch size
- Flush more frequently
- Clear ring buffer periodically

---

## Success Metrics

### Week 1 Metrics

- **Packet Loss:** < 0.1%
- **Position Error:** < 5m at 10 knots
- **Uptime:** 24 hours continuous
- **CPU:** < 50%
- **Memory:** < 4GB

### Week 2 Metrics

- **Write Throughput:** 1M+ pings/hour
- **Data Quality:** 90%+ GPS quality
- **Compression Ratio:** > 5:1
- **Query Performance:** < 1s for any day
- **Storage Efficiency:** Parquet < 20% raw size

### Week 3-4 Metrics

- **Uptime:** 99%+ during operations
- **TZ Pro Impact:** Zero (non-disruptive)
- **Auto-Start:** 100% with TimeZero
- **Health Reports:** Daily generating
- **Data Retention:** Auto-purge working

---

## Emergency Procedures

### Data Loss Prevention

**If packet loss detected:**
1. Check ring buffer size (increase capacity)
2. Verify BPF filter is correct
3. Check system resources (CPU/memory)
4. Restart capture daemon

**If GPS gaps detected:**
1. Check NMEA serial connection
2. Verify GPS antenna signal
3. Check quality flags in data
4. Enable dead reckoning backup

### System Recovery

**If daemon crashes:**
1. Check error logs
2. Verify configuration
3. Restart daemon
4. Monitor for 10 minutes

**If storage fails:**
1. Check disk space
2. Verify directory permissions
3. Test Parquet write
4. Restart storage pipeline

---

## Next Steps After Phase 0

After 30 days, proceed to:

1. **Phase 1 (Physical Tensors):** Normalization, calibration, H3 indexing
2. **Phase 2 (Analytical Features):** Feature extraction, classification
3. **Phase 3 (Operational Intelligence):** Prediction, recommendation
4. **Phase 4 (Strategic Knowledge):** Stock assessment, ecosystem

**Critical:** Phase 0 must be bulletproof before proceeding. The acoustic signatures of 2026 cannot be recreated in 2031.

---

## Support & Documentation

**Full Implementation Plan:** `phase0_implementation_plan.md`
**Memory Schema:** `vessel_agent_memory_schema.json`
**Knowledge Base:** `vessel_agent_knowledge_base.md`
**5-Year Vision:** `vessel_agent_5year_vision.md`

**For Questions:**
- Check troubleshooting section first
- Review full implementation plan
- Check error logs in `C:\data\vessel_agent\logs\`
- Run diagnostics: `python capture_daemon.py doctor`

---

**Version:** 1.0.0
**Status:** Production Ready
**Deploy:** Immediately on F/V EILEEN
**Timeline:** 30 Days (Phase 0)
**Priority:** CRITICAL - Data Capture Emergency
