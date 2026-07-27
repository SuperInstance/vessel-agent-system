"""Async NMEA 0183 bridge for AELMA.

This module provides :class:`NMEABridge`, an ``asyncio`` server that:

1. Listens on a **plain TCP** socket for newline-delimited NMEA 0183
   sentences (the format emitted by virtually every marine instrument).
2. For each sentence: parses it, assigns ``timestamp_ns`` from the
   system monotonic clock, runs a :func:`quality.check_quality` sanity
   check, and builds a telemetry-packet dict matching
   ``telemetry_packet.schema.json``.
3. Serves **WebSocket** clients on a separate port.  Every new packet is
   broadcast as JSON to all connected subscribers.  When a client
   connects it immediately receives the last-known reading for every
   channel (the "last-seen" cache).

The bridge is intentionally graceful about malformed input: a bad
checksum or unparseable sentence is logged and dropped, never crashes
the server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection

from . import nmea
from . import quality

logger = logging.getLogger("aelma.bridge")

# Type alias for a telemetry packet dict.
Packet = dict[str, Any]


def build_packet(reading: dict[str, Any]) -> Packet:
    """Build a full telemetry-packet dict from a parser reading.

    Adds ``timestamp_ns`` and ``quality`` to the base reading.
    """
    ts = time.time_ns()
    q = quality.check_quality(reading["channel"], reading["value"])
    return {
        "timestamp_ns": ts,
        "source": reading["source"],
        "channel": reading["channel"],
        "value": reading["value"],
        "quality": q,
        "sentence": reading.get("sentence"),
    }


class NMEABridge:
    """Async bridge: TCP (NMEA in) + WebSocket (telemetry out).

    Args:
        tcp_port: Port for the plain-TCP NMEA listener.
        ws_port:  Port for the WebSocket telemetry server.
    """

    def __init__(self, tcp_port: int = 8001, ws_port: int = 8000) -> None:
        self.tcp_port = tcp_port
        self.ws_port = ws_port
        # Connected WebSocket clients.
        self._ws_clients: set[ServerConnection] = set()
        # Last-seen packet per channel (for new-subscriber catch-up).
        self._last_seen: dict[str, Packet] = {}
        self._tcp_server: asyncio.base_events.Server | None = None
        self._ws_server: Any = None
        self._stopping = False

    # ------------------------------------------------------------------
    # Packet handling
    # ------------------------------------------------------------------

    async def ingest_line(self, line: str) -> list[Packet]:
        """Parse one raw NMEA line, update caches, and broadcast.

        Returns the list of packets created (may be empty).
        """
        line = line.strip()
        if not line:
            return []
        try:
            readings = nmea.parse_sentence(line)
        except ValueError as exc:
            logger.warning("Bad sentence dropped: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001 -- defensive
            logger.warning("Unexpected parse error on %r: %s", line, exc)
            return []
        packets: list[Packet] = []
        for reading in readings:
            pkt = build_packet(reading)
            packets.append(pkt)
            self._last_seen[pkt["channel"]] = pkt
            logger.debug("Packet: %s", pkt)
        if packets:
            await self._broadcast(packets)
        return packets

    # ------------------------------------------------------------------
    # WebSocket broadcast
    # ------------------------------------------------------------------

    async def _broadcast(self, packets: list[Packet]) -> None:
        """Send JSON packets to every connected WebSocket client."""
        if not self._ws_clients:
            return
        messages = [json.dumps(pkt) for pkt in packets]
        # Snapshot to avoid mutation during iteration.
        clients = list(self._ws_clients)
        for client in clients:
            for msg in messages:
                try:
                    await client.send(msg)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("WS send failed, dropping client: %s", exc)
                    self._ws_clients.discard(client)

    # ------------------------------------------------------------------
    # TCP NMEA listener
    # ------------------------------------------------------------------

    async def _handle_tcp_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle one TCP NMEA stream connection."""
        peer = writer.get_extra_info("peername")
        logger.info("TCP NMEA client connected: %s", peer)
        try:
            while not self._stopping:
                line_bytes = await reader.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("ascii", errors="replace")
                await self.ingest_line(line)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("TCP client error from %s: %s", peer, exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            logger.info("TCP NMEA client disconnected: %s", peer)

    # ------------------------------------------------------------------
    # WebSocket handler
    # ------------------------------------------------------------------

    async def _handle_ws_client(self, websocket: ServerConnection) -> None:
        """Handle a WebSocket subscriber connection."""
        self._ws_clients.add(websocket)
        logger.info("WS subscriber connected: %s", websocket.remote_address)
        # Send last-seen packets so the new client is immediately current.
        for pkt in self._last_seen.values():
            try:
                await websocket.send(json.dumps(pkt))
            except Exception:  # noqa: BLE001
                self._ws_clients.discard(websocket)
                return
        try:
            # Keep the connection open; we don't expect inbound messages
            # but we must await to keep the handler alive.
            async for _ in websocket:
                pass
        except websockets.ConnectionClosed:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("WS handler error: %s", exc)
        finally:
            self._ws_clients.discard(websocket)
            logger.info("WS subscriber disconnected: %s", websocket.remote_address)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the TCP and WebSocket servers."""
        self._tcp_server = await asyncio.start_server(
            self._handle_tcp_client, host="0.0.0.0", port=self.tcp_port
        )
        self._ws_server = await websockets.serve(
            self._handle_ws_client, "0.0.0.0", self.ws_port
        )
        logger.info(
            "Bridge started -- TCP NMEA on :%d, WebSocket on :%d",
            self.tcp_port,
            self.ws_port,
        )

    async def serve_forever(self) -> None:
        """Run both servers until stopped."""
        await self.start()
        try:
            # Block until the TCP server (and thus the event loop) closes.
            if self._tcp_server is not None:
                await self._tcp_server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Shut down both servers gracefully."""
        self._stopping = True
        if self._tcp_server is not None:
            self._tcp_server.close()
            await self._tcp_server.wait_closed()
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        logger.info("Bridge stopped.")


def run(tcp_port: int = 8001, ws_port: int = 8000, debug: bool = False) -> None:
    """Entry point: configure logging and run the bridge."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    bridge = NMEABridge(tcp_port=tcp_port, ws_port=ws_port)
    try:
        asyncio.run(bridge.serve_forever())
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down.")
