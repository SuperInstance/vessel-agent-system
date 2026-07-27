"""CLI entry point for the AELMA bridge.

Usage:
    python -m bridge --tcp-port 8001 --ws-port 8000 --debug
"""

from __future__ import annotations

import argparse

from .bridge import run


def main() -> None:
    """Parse CLI args and start the bridge."""
    parser = argparse.ArgumentParser(
        prog="bridge",
        description="AELMA NMEA 0183 bridge: TCP in, WebSocket out.",
    )
    parser.add_argument(
        "--tcp-port",
        type=int,
        default=8001,
        help="Port for the plain-TCP NMEA 0183 listener (default: 8001).",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=8000,
        help="Port for the WebSocket telemetry server (default: 8000).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug-level logging.",
    )
    args = parser.parse_args()
    run(tcp_port=args.tcp_port, ws_port=args.ws_port, debug=args.debug)


if __name__ == "__main__":
    main()
