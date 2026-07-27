"""CLI entry point: ``python -m bridge [--tcp-port N] [--ws-port N] [--debug]``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .bridge import amain


def main(argv: list[str] | None = None) -> int:
    """Parse args, configure logging, and run the bridge until Ctrl-C."""
    parser = argparse.ArgumentParser(
        prog="bridge",
        description="AELMA bridge: NMEA 0183 TCP -> telemetry WebSocket.",
    )
    parser.add_argument("--tcp-port", type=int, default=8001,
                        help="TCP port for NMEA 0183 input (default 8001)")
    parser.add_argument("--ws-port", type=int, default=8000,
                        help="WebSocket port for telemetry output (default 8000)")
    parser.add_argument("--debug", action="store_true",
                        help="enable debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        asyncio.run(amain(tcp_port=args.tcp_port, ws_port=args.ws_port))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
