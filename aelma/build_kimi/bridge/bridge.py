"""AELMA bridge: NMEA 0183 over TCP in, telemetry packets over WebSocket out.

The bridge listens on a plain TCP port (default 8001) for newline-
terminated NMEA 0183 sentences from the vessel bus (or a simulator),
and serves WebSocket subscribers (default port 8000) with JSON
telemetry packets matching ``telemetry_packet.schema.json``.

Pipeline per NMEA line:
    parse -> assign timestamp_ns = time.time_ns() -> quality check
    -> build packet -> broadcast to all WebSocket subscribers.

The last packet seen per channel is cached and replayed to each new
subscriber on connect, so late joiners get current vessel state.
Malformed sentences are logged and dropped; they never kill a
connection. Logs go to stderr.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from websockets.asyncio.server import ServerConnection, serve

from .nmea import parse_sentence
from .quality import check_quality

log = logging.getLogger("aelma.bridge")


def build_packet(reading: dict[str, Any], timestamp_ns: int) -> dict[str, Any]:
    """Turn one parsed reading into a schema-conformant telemetry packet."""
    return {
        "timestamp_ns": timestamp_ns,
        "source": reading["source"],
        "channel": reading["channel"],
        "value": reading["value"],
        "quality": check_quality(reading["channel"], reading["value"]),
        "sentence": reading["sentence"],
    }


class Bridge:
    """Holds server state: subscriber set and last-seen channel cache."""

    def __init__(self) -> None:
        self.subscribers: set[ServerConnection] = set()
        self.last_seen: dict[str, dict[str, Any]] = {}

    async def handle_nmea_line(self, line: str) -> list[dict[str, Any]]:
        """Parse one raw line and broadcast resulting packets.

        Returns the packets emitted (empty for malformed or
        uninformative lines). Never raises on bad input.
        """
        line = line.strip()
        if not line:
            return []
        try:
            readings = parse_sentence(line)
        except ValueError as exc:
            log.warning("dropping malformed sentence: %s", exc)
            return []
        ts = time.time_ns()
        packets = [build_packet(r, ts) for r in readings]
        for pkt in packets:
            self.last_seen[pkt["channel"]] = pkt
        if packets:
            log.debug(
                "ingest %s -> %d packet(s) for %s",
                line, len(packets), [p["channel"] for p in packets],
            )
            await self.broadcast(packets)
        return packets

    async def broadcast(self, packets: list[dict[str, Any]]) -> None:
        """Send packets to every connected WebSocket subscriber."""
        if not self.subscribers:
            return
        messages = [json.dumps(p) for p in packets]
        results = await asyncio.gather(
            *(ws.send(m) for m in messages for ws in self.subscribers),
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                log.debug("send to subscriber failed: %s", r)

    async def ws_handler(self, ws: ServerConnection) -> None:
        """Register a subscriber, replay last-seen state, hold until close."""
        peer = ws.remote_address
        self.subscribers.add(ws)
        log.info("subscriber connected: %s (%d total)", peer, len(self.subscribers))
        try:
            for pkt in self.last_seen.values():
                await ws.send(json.dumps(pkt))
            # We never expect client messages; just wait for disconnect.
            async for _ in ws:
                pass
        finally:
            self.subscribers.discard(ws)
            log.info("subscriber disconnected: %s (%d left)", peer, len(self.subscribers))

    async def tcp_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Consume newline-delimited NMEA sentences from one TCP client."""
        peer = writer.get_extra_info("peername")
        log.info("NMEA TCP client connected: %s", peer)
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                try:
                    line = raw.decode("ascii", errors="replace")
                except UnicodeDecodeError:  # pragma: no cover - replaced above
                    continue
                await self.handle_nmea_line(line)
        except (ConnectionResetError, BrokenPipeError):
            log.info("NMEA TCP client reset: %s", peer)
        finally:
            writer.close()
            log.info("NMEA TCP client disconnected: %s", peer)

    async def run(self, tcp_port: int = 8001, ws_port: int = 8000) -> None:
        """Start both servers and run until cancelled."""
        tcp_server = await asyncio.start_server(self.tcp_handler, "0.0.0.0", tcp_port)
        ws_server = await serve(self.ws_handler, "0.0.0.0", ws_port)
        log.info("bridge up: NMEA TCP on :%d, WebSocket on :%d", tcp_port, ws_port)
        async with tcp_server, ws_server:
            await asyncio.gather(
                tcp_server.serve_forever(), ws_server.serve_forever()
            )


async def amain(tcp_port: int, ws_port: int) -> None:
    """Entry point used by the CLI; wraps Bridge.run."""
    bridge = Bridge()
    try:
        await bridge.run(tcp_port=tcp_port, ws_port=ws_port)
    except asyncio.CancelledError:
        log.info("bridge shutting down")
        raise
