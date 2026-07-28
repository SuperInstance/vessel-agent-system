"""Async NMEA 0183 and Signal K bridge for AELMA.

This module provides :class:`NMEABridge` and :class:`SignalKBridge`,
``asyncio`` servers that:

1. **NMEABridge**: Listens on a **plain TCP** socket for newline-delimited
   NMEA 0183 sentences (the format emitted by virtually every marine
   instrument).  For each sentence: parses it, assigns ``timestamp_ns`` from
   the system monotonic clock, runs a :func:`quality.check_quality` sanity
   check, and builds a telemetry-packet dict matching
   ``telemetry_packet.schema.json``.

2. **SignalKBridge**: Connects as a WebSocket **client** to a Signal K server,
   receives delta updates, parses them, and converts them to telemetry packets.
   Also provides a TCP server for direct Signal K JSON connections.

3. Both serve **WebSocket** clients on a separate port.  Every new packet is
   broadcast as JSON to all connected subscribers.  When a client connects it
   immediately receives the last-known reading for every channel (the
   "last-seen" cache).

The bridges are intentionally graceful about malformed input: bad checksums,
unparseable sentences, or invalid JSON are logged and dropped, never crash the
servers.
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
from . import signalk

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


# ---------------------------------------------------------------------------
# Signal K Bridge
# ---------------------------------------------------------------------------


class SignalKBridge:
    """Async bridge: Signal K WebSocket client + TCP server + WebSocket telemetry out.

    This bridge connects to a Signal K server as a WebSocket client, receives
    delta updates, parses them, and broadcasts them as telemetry packets.

    Args:
        signalk_host: Signal K server hostname or IP.
        signalk_port: Signal K server WebSocket port.
        signalk_tcp_port: Port for the Signal K TCP listener (direct JSON deltas).
        telemetry_ws_port: Port for the WebSocket telemetry server (output).
    """

    def __init__(
        self,
        signalk_host: str = "localhost",
        signalk_port: int = 3000,
        signalk_tcp_port: int = 8002,
        telemetry_ws_port: int = 8000,
    ) -> None:
        self.signalk_host = signalk_host
        self.signalk_port = signalk_port
        self.signalk_tcp_port = signalk_tcp_port
        self.telemetry_ws_port = telemetry_ws_port

        # Connected WebSocket clients (telemetry subscribers).
        self._ws_clients: set[ServerConnection] = set()
        # Last-seen packet per channel (for new-subscriber catch-up).
        self._last_seen: dict[str, Packet] = {}

        # Servers
        self._tcp_server: asyncio.base_events.Server | None = None
        self._telemetry_ws_server: Any = None

        # Signal K WebSocket client connection
        self._sk_ws_client: Any = None
        self._sk_reconnect_task: asyncio.Task | None = None
        self._stopping = False

    # ------------------------------------------------------------------
    # Packet handling
    # ------------------------------------------------------------------

    async def ingest_delta(self, delta_data: dict | str) -> list[Packet]:
        """Parse one Signal K delta, update caches, and broadcast.

        Returns the list of packets created (may be empty).
        """
        try:
            readings = signalk.parse_delta(delta_data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Bad Signal K delta dropped: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001 -- defensive
            logger.warning("Unexpected parse error on Signal K delta: %s", exc)
            return []

        packets: list[Packet] = []
        for reading in readings:
            pkt = build_packet(reading)
            packets.append(pkt)
            self._last_seen[pkt["channel"]] = pkt
            logger.debug("Signal K Packet: %s", pkt)
        if packets:
            await self._broadcast(packets)
        return packets

    # ------------------------------------------------------------------
    # WebSocket broadcast (telemetry output)
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
    # Signal K WebSocket client (input)
    # ------------------------------------------------------------------

    async def _connect_signalk(self) -> None:
        """Connect to Signal K server and consume delta updates."""
        uri = signalk.signalk_ws_endpoint(self.signalk_host, self.signalk_port)
        logger.info("Connecting to Signal K server: %s", uri)

        while not self._stopping:
            try:
                async with websockets.asyncio.client.connect(uri) as websocket:
                    self._sk_ws_client = websocket
                    logger.info("Connected to Signal K server: %s", uri)

                    async for message in websocket:
                        if self._stopping:
                            break
                        try:
                            # Parse delta from JSON message
                            delta_data = json.loads(message)
                            await self.ingest_delta(delta_data)
                        except json.JSONDecodeError as exc:
                            logger.warning("Invalid JSON from Signal K: %s", exc)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("Error processing Signal K message: %s", exc)

            except websockets.ConnectionClosed:
                logger.warning("Signal K connection closed, reconnecting...")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Signal K connection error: %s, reconnecting...", exc)
            finally:
                self._sk_ws_client = None

            if not self._stopping:
                # Wait before reconnecting
                await asyncio.sleep(5)

    # ------------------------------------------------------------------
    # TCP Signal K listener (input)
    # ------------------------------------------------------------------

    async def _handle_tcp_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle one TCP Signal K stream connection (newline-delimited JSON deltas)."""
        peer = writer.get_extra_info("peername")
        logger.info("TCP Signal K client connected: %s", peer)
        try:
            while not self._stopping:
                line_bytes = await reader.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                try:
                    delta_data = json.loads(line)
                    await self.ingest_delta(delta_data)
                except json.JSONDecodeError as exc:
                    logger.warning("Invalid JSON from TCP Signal K client %s: %s", peer, exc)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("TCP Signal K client error from %s: %s", peer, exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            logger.info("TCP Signal K client disconnected: %s", peer)

    # ------------------------------------------------------------------
    # WebSocket handler (telemetry output)
    # ------------------------------------------------------------------

    async def _handle_telemetry_ws_client(self, websocket: ServerConnection) -> None:
        """Handle a WebSocket telemetry subscriber connection."""
        self._ws_clients.add(websocket)
        logger.info("WS telemetry subscriber connected: %s", websocket.remote_address)
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
            logger.warning("WS telemetry handler error: %s", exc)
        finally:
            self._ws_clients.discard(websocket)
            logger.info("WS telemetry subscriber disconnected: %s", websocket.remote_address)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the TCP and telemetry WebSocket servers, and Signal K client."""
        # Start TCP server for direct Signal K JSON connections
        self._tcp_server = await asyncio.start_server(
            self._handle_tcp_client, host="0.0.0.0", port=self.signalk_tcp_port
        )

        # Start telemetry WebSocket server
        self._telemetry_ws_server = await websockets.serve(
            self._handle_telemetry_ws_client, "0.0.0.0", self.telemetry_ws_port
        )

        # Start Signal K WebSocket client connection
        self._sk_reconnect_task = asyncio.create_task(self._connect_signalk())

        logger.info(
            "Signal K Bridge started -- TCP Signal K on :%d, Signal K client: %s:%d, Telemetry WebSocket on :%d",
            self.signalk_tcp_port,
            self.signalk_host,
            self.signalk_port,
            self.telemetry_ws_port,
        )

    async def serve_forever(self) -> None:
        """Run all servers until stopped."""
        await self.start()
        try:
            # Keep the reconnection task running
            if self._sk_reconnect_task:
                await self._sk_reconnect_task
            # Block until the TCP server closes
            if self._tcp_server is not None:
                await self._tcp_server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Shut down all servers and connections gracefully."""
        self._stopping = True
        if self._tcp_server is not None:
            self._tcp_server.close()
            await self._tcp_server.wait_closed()
        if self._telemetry_ws_server is not None:
            self._telemetry_ws_server.close()
            await self._telemetry_ws_server.wait_closed()
        if self._sk_ws_client is not None:
            await self._sk_ws_client.close()
        if self._sk_reconnect_task:
            self._sk_reconnect_task.cancel()
            try:
                await self._sk_reconnect_task
            except asyncio.CancelledError:
                pass
        logger.info("Signal K Bridge stopped.")


def run_signalk(
    signalk_host: str = "localhost",
    signalk_port: int = 3000,
    signalk_tcp_port: int = 8002,
    telemetry_ws_port: int = 8000,
    debug: bool = False,
) -> None:
    """Entry point: configure logging and run the Signal K bridge."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    bridge = SignalKBridge(
        signalk_host=signalk_host,
        signalk_port=signalk_port,
        signalk_tcp_port=signalk_tcp_port,
        telemetry_ws_port=telemetry_ws_port,
    )
    try:
        asyncio.run(bridge.serve_forever())
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down.")
