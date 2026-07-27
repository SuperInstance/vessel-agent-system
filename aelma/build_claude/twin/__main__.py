"""CLI entry point for the AELMA twin core.

Usage::

    python -m twin --bridge-url ws://localhost:8000 \\
                   --viewer-port 8090 \\
                   --vessel-id US-AK-FVEILEEN-51 \\
                   --bathymetry-path bathymetry.json \\
                   --broadcast-interval 1.0
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .core import TwinCore


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv
        Optional argument list (defaults to ``sys.argv[1:]``).

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        prog="twin",
        description="AELMA digital twin core for the F/V EILEEN.",
    )
    parser.add_argument(
        "--bridge-url",
        default="ws://localhost:8000",
        help="WebSocket URL of the AELMA bridge (default: ws://localhost:8000)",
    )
    parser.add_argument(
        "--viewer-port",
        type=int,
        default=8090,
        help="TCP port for viewer WebSocket server (default: 8090)",
    )
    parser.add_argument(
        "--vessel-id",
        default="US-AK-FVEILEEN-51",
        help="ISO-style vessel identifier (default: US-AK-FVEILEEN-51)",
    )
    parser.add_argument(
        "--bathymetry-path",
        default="bathymetry.json",
        help="Path for bathymetry JSON persistence (default: bathymetry.json)",
    )
    parser.add_argument(
        "--broadcast-interval",
        type=float,
        default=1.0,
        help="Seconds between snapshot broadcasts (default: 1.0)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the twin core.

    Parameters
    ----------
    argv
        Optional argument list.

    Returns
    -------
    int
        Process exit code (0 on clean shutdown).
    """
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    core = TwinCore(
        bridge_url=args.bridge_url,
        viewer_port=args.viewer_port,
        vessel_id=args.vessel_id,
        bathymetry_path=args.bathymetry_path,
        broadcast_interval=args.broadcast_interval,
    )

    try:
        asyncio.run(core.run())
    except KeyboardInterrupt:
        logging.getLogger("aelma.twin").info("Shutting down (KeyboardInterrupt).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
