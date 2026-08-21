#!/usr/bin/env python
"""AELMA Sensor Capture standalone service."""

import asyncio
import logging
from pathlib import Path
from twin.sensors.nmea_udp_capture import SensorCaptureCoordinator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("aelma.sensors")


async def main():
    """Run sensor capture service."""

    # Create sensor coordinator
    coordinator = SensorCaptureCoordinator(
        nmea_jsonl="sensor_data/nmea_telemetry.jsonl",
        depth_jsonl="sensor_data/depth_sounder.jsonl",
        radar_jsonl="sensor_data/radar.jsonl",
        log_path="sensor_data/sensor_capture.log",
    )

    log.info("Starting AELMA Sensor Capture Service")
    log.info("=" * 50)

    # Start NMEA listener
    coordinator.start_nmea_listener(host="0.0.0.0", port=8001)
    log.info("✓ NMEA 0183 TCP listener: 0.0.0.0:8001")

    # Start UDP depth listener
    coordinator.start_udp_depth(host="0.0.0.0", port=50000)
    log.info("✓ UDP Depth listener: 0.0.0.0:50000")

    # Start radar listener (optional)
    coordinator.start_radar(host="0.0.0.0", port=50001)
    log.info("✓ UDP Radar listener: 0.0.0.0:50001")

    log.info("=" * 50)
    log.info("Sensor capture active - Press Ctrl+C to stop")
    log.info("")

    # Create sensor data directory if not exists
    Path("sensor_data").mkdir(exist_ok=True)

    try:
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

            # Print status every 30 seconds
            if int(asyncio.get_event_loop().time()) % 30 == 0:
                status = coordinator.get_status()
                log.info("Status: NMEA=%s, Depth=%s, Radar=%s",
                         status.get("nmea_listener", "off"),
                         status.get("udp_depth_listener", "off"),
                         status.get("radar_listener", "off"))

    except KeyboardInterrupt:
        log.info("Shutting down sensor capture...")
        coordinator.stop_all()
        log.info("Sensor capture stopped")


if __name__ == "__main__":
    asyncio.run(main())
