#!/usr/bin/env python
"""AELMA TwinCore startup script with sensor capture enabled."""

import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("aelma.startup")

# Import TwinCore after logging is configured
from twin.core import TwinCore


async def main():
    """Start TwinCore with sensor capture enabled."""

    # Create TwinCore instance with sensor capture
    core = TwinCore(
        bridge_url="ws://localhost:8000",
        viewer_port=8090,
        vessel_id="US-AK-FVEILEEN-51",
        bathymetry_path="bathymetry.json",
        broadcast_interval=1.0,
        persist_interval=60.0,
        viewport_radius_m=500.0,

        # Sensor capture configuration
        enable_sensors=True,
        nmea_port=8001,
        udp_depth_port=50000,
        sensor_output_dir="sensor_data",

        # Existing configuration
        quota_path="quota",
        quota_enabled=True,
        mob_events_path="mob_events.jsonl",
        enable_mob=True,
        crew_fatigue_path="crew_fatigue",
        enable_crew_fatigue=True,
        equipment_path="equipment",
        enable_equipment=True,

        # Health and metrics (disabled - already running)
        health_port=None,  # Already running
        metrics_port=None,  # Already running

        # JEPA configuration
        enable_jepa=True,
        jepa_history_size=1000,
        jepa_learning_rate=0.1,
        jepa_anomaly_threshold=2.5,
    )

    log.info("Starting AELMA TwinCore for F/V EILEEN")
    log.info("Bridge URL: %s", core.bridge_url)
    log.info("Viewer port: %s", core.viewer_port)
    log.info("")
    log.info("Sensor Capture:")
    log.info("  NMEA 0183 TCP: port %s", 8001)
    log.info("  UDP Depth: port %s", 50000)
    log.info("  Output: sensor_data/")
    log.info("")
    log.info("Press Ctrl+C to stop")

    try:
        await core.run()
    except KeyboardInterrupt:
        log.info("Shutting down...")
    except Exception as e:
        log.error("TwinCore error: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
