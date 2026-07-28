"""CLI entry point: ``python -m build_kimi.twin``."""

from __future__ import annotations

import argparse
import asyncio
import logging

from .core import TwinCore


def main() -> None:
    """Parse arguments and run the twin until interrupted."""
    parser = argparse.ArgumentParser(
        prog="aelma-twin",
        description="AELMA twin core: digital twin for the F/V EILEEN.",
    )
    parser.add_argument("--bridge-url", default="ws://localhost:8000",
                        help="WebSocket URL of the telemetry bridge.")
    parser.add_argument("--viewer-port", type=int, default=8090,
                        help="Port for the viewer WebSocket server.")
    parser.add_argument("--vessel-id", default="US-AK-FVEILEEN-51",
                        help="Vessel identifier for snapshots.")
    parser.add_argument("--bathymetry-path", default="bathymetry.json",
                        help="Path for bathymetry grid persistence.")
    parser.add_argument("--broadcast-interval", type=float, default=1.0,
                        help="Seconds between snapshot broadcasts.")
    parser.add_argument("--persist-interval", type=float, default=60.0,
                        help="Seconds between bathymetry saves.")
    parser.add_argument("--viewport-radius-m", type=float, default=500.0,
                        help="Bathymetry viewport radius in meters.")
    parser.add_argument("--health-port", type=int, default=8091,
                        help="Port for the health HTTP server (/health, /ready, /live).")
    parser.add_argument("--metrics-port", type=int, default=9090,
                        help="Port for the Prometheus /metrics endpoint (0 disables).")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    core = TwinCore(
        bridge_url=args.bridge_url,
        viewer_port=args.viewer_port,
        vessel_id=args.vessel_id,
        bathymetry_path=args.bathymetry_path,
        broadcast_interval=args.broadcast_interval,
        persist_interval=args.persist_interval,
        viewport_radius_m=args.viewport_radius_m,
        health_port=args.health_port,
        metrics_port=args.metrics_port or None,
    )
    try:
        asyncio.run(core.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
