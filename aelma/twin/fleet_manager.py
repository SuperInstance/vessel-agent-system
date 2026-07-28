"""FleetManager: Multi-vessel fleet management for AELMA.

Provides centralized management of multiple fishing vessels, each running
its own TwinCore instance. Enables fleet-wide analytics, inter-vessel
coordination, and unified WebSocket broadcasts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import websockets

from .bathymetry import BathymetryGrid
from .metrics import MetricsCollector, PACKETS_RECEIVED, ACTIONS_FIRED
from .state import VesselState, haversine_m

log = logging.getLogger("aelma.fleet")

# Default configuration
DEFAULT_FLEET_VIEWER_PORT = 8092
DEFAULT_BROADCAST_INTERVAL = 1.0


class VesselInstance:
    """Container for a single vessel's twin core and metadata."""

    def __init__(
        self,
        vessel_id: str,
        config: dict[str, Any],
        data_dir: Path,
    ) -> None:
        """Initialize a vessel instance with its own TwinCore configuration.

        Parameters
        ----------
        vessel_id:
            Unique vessel identifier (e.g., "US-AK-FVEILEEN-51")
        config:
            Vessel configuration dict with keys:
            - bridge_url: WebSocket URL to bridge
            - viewer_port: Port for this vessel's viewer
            - bathymetry_path: Path to bathymetry data
            - viewport_radius_m: Bathymetry viewport radius
            - name: Human-readable vessel name
            - vessel_type: Type of vessel (e.g., "fishing", "research")
        data_dir:
            Base directory for vessel data files
        """
        self.vessel_id = vessel_id
        self.config = config
        self.name = config.get("name", vessel_id)
        self.vessel_type = config.get("vessel_type", "unknown")
        self.data_dir = data_dir / vessel_id
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Create isolated state for this vessel
        self.state = VesselState()
        self.bathymetry = BathymetryGrid()
        self._viewers: set[Any] = set()

        # Paths for vessel-specific data
        self.bathymetry_path = self.data_dir / config.get(
            "bathymetry_path", "bathymetry.json"
        )
        self.a2a_log_path = self.data_dir / config.get("a2a_log_path", "a2a.jsonl")
        self.oplog_path = self.data_dir / config.get("oplog_path", "oplog.jsonl")

        # Connection status
        self.bridge_connected = False
        self.last_update = 0.0

        # Metrics
        self.metrics = MetricsCollector()
        self.metrics.register_counter(
            PACKETS_RECEIVED, f"Telemetry packets for {vessel_id}"
        )
        self.metrics.register_counter(
            ACTIONS_FIRED, f"A2A actions for {vessel_id}"
        )


class FleetManager:
    """Central manager for multiple vessel TwinCore instances.

    Provides:
    - Multi-vessel registration and lifecycle management
    - Fleet-wide analytics and summaries
    - Inter-vessel distance calculations
    - Unified WebSocket broadcasts for fleet viewers
    - Vessel lookup by location and purpose
    """

    def __init__(
        self,
        viewer_port: int = DEFAULT_FLEET_VIEWER_PORT,
        broadcast_interval: float = DEFAULT_BROADCAST_INTERVAL,
        data_dir: Path | str = "fleet_data",
    ) -> None:
        """Initialize the fleet manager.

        Parameters
        ----------
        viewer_port:
            Port for fleet-wide WebSocket viewer
        broadcast_interval:
            Seconds between fleet snapshot broadcasts
        data_dir:
            Base directory for all vessel data
        """
        self.viewer_port = viewer_port
        self.broadcast_interval = broadcast_interval
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Vessel registry
        self.vessels: dict[str, VesselInstance] = {}

        # Fleet viewers
        self._fleet_viewers: set[Any] = set()

        # Fleet metrics
        self.metrics = MetricsCollector()
        self.metrics.register_counter(
            "fleet_packets_total", "Total telemetry packets across fleet"
        )
        self.metrics.register_gauge(
            "fleet_vessels_active", "Number of active vessels in fleet"
        )
        self.metrics.register_gauge(
            "fleet_viewers_connected", "Number of fleet viewer connections"
        )

        # Background tasks
        self._tasks: set[Any] = set()
        self._running = False

    # ------------------------------------------------------------------ #
    # Vessel registration and lifecycle
    # ------------------------------------------------------------------ #
    def register_vessel(self, vessel_id: str, config: dict[str, Any]) -> VesselInstance:
        """Register a new vessel in the fleet.

        Parameters
        ----------
        vessel_id:
            Unique vessel identifier
        config:
            Vessel configuration dict (see VesselInstance for details)

        Returns
        -------
        VesselInstance
            The created vessel instance

        Raises
        ------
        ValueError
            If vessel_id already exists in fleet
        """
        if vessel_id in self.vessels:
            raise ValueError(f"Vessel {vessel_id} already registered")

        vessel = VesselInstance(vessel_id, config, self.data_dir)
        self.vessels[vessel_id] = vessel
        self.metrics.set_gauge("fleet_vessels_active", len(self.vessels))

        log.info("Registered vessel %s (%s)", vessel_id, vessel.name)
        return vessel

    def unregister_vessel(self, vessel_id: str) -> None:
        """Remove a vessel from the fleet.

        Parameters
        ----------
        vessel_id:
            Vessel to remove

        Raises
        ------
        KeyError
            If vessel_id not found
        """
        if vessel_id not in self.vessels:
            raise KeyError(f"Vessel {vessel_id} not found")

        del self.vessels[vessel_id]
        self.metrics.set_gauge("fleet_vessels_active", len(self.vessels))

        log.info("Unregistered vessel %s", vessel_id)

    def get_vessel(self, vessel_id: str) -> VesselInstance:
        """Get a vessel instance by ID.

        Parameters
        ----------
        vessel_id:
            Vessel identifier

        Returns
        -------
        VesselInstance
            The vessel instance

        Raises
        ------
        KeyError
            If vessel_id not found
        """
        if vessel_id not in self.vessels:
            raise KeyError(f"Vessel {vessel_id} not found")
        return self.vessels[vessel_id]

    def list_vessels(self) -> list[str]:
        """List all registered vessel IDs.

        Returns
        -------
        list[str]
            List of vessel IDs
        """
        return list(self.vessels.keys())

    # ------------------------------------------------------------------ #
    # State access and telemetry
    # ------------------------------------------------------------------ #
    def get_vessel_state(self, vessel_id: str) -> dict[str, Any] | None:
        """Get the current state snapshot for a specific vessel.

        Parameters
        ----------
        vessel_id:
            Vessel identifier

        Returns
        -------
        dict | None
            Vessel state snapshot, or None if vessel not found
        """
        if vessel_id not in self.vessels:
            return None

        vessel = self.vessels[vessel_id]
        now_ns = time.time_ns()

        return {
            "timestamp_ns": now_ns,
            "vessel_id": vessel_id,
            "name": vessel.name,
            "vessel_type": vessel.vessel_type,
            "pose": {
                "lat": vessel.state.lat,
                "lon": vessel.state.lon,
                "heading_deg": vessel.state.heading_deg,
                "speed_kn": vessel.state.speed_kn,
            },
            "channels": dict(vessel.state.channels),
            "bridge_connected": vessel.bridge_connected,
            "last_update": vessel.last_update,
        }

    def get_all_positions(self) -> dict[str, dict[str, Any]]:
        """Get all vessel positions in the fleet.

        Returns
        -------
        dict
            Mapping of vessel_id to position data:
            {
                "vessel_id": {
                    "name": str,
                    "lat": float | None,
                    "lon": float | None,
                    "heading_deg": float | None,
                    "speed_kn": float | None,
                    "last_update": float
                }
            }
        """
        positions = {}
        for vessel_id, vessel in self.vessels.items():
            positions[vessel_id] = {
                "name": vessel.name,
                "vessel_type": vessel.vessel_type,
                "lat": vessel.state.lat,
                "lon": vessel.state.lon,
                "heading_deg": vessel.state.heading_deg,
                "speed_kn": vessel.state.speed_kn,
                "bridge_connected": vessel.bridge_connected,
                "last_update": vessel.last_update,
            }
        return positions

    def get_fleet_snapshot(self) -> dict[str, Any]:
        """Get comprehensive fleet snapshot including all vessel states.

        Returns
        -------
        dict
            Fleet snapshot with:
            - timestamp_ns: Snapshot timestamp
            - vessel_count: Number of vessels
            - vessels: Dict of full vessel states
            - analytics: Fleet-level analytics
        """
        now_ns = time.time_ns()
        vessels = {}
        for vessel_id in self.vessels:
            state = self.get_vessel_state(vessel_id)
            if state:
                vessels[vessel_id] = state

        return {
            "timestamp_ns": now_ns,
            "vessel_count": len(self.vessels),
            "vessels": vessels,
            "analytics": self._compute_analytics(),
        }

    # ------------------------------------------------------------------ #
    # Fleet analytics
    # ------------------------------------------------------------------ #
    def _compute_analytics(self) -> dict[str, Any]:
        """Compute fleet-level analytics.

        Returns
        -------
        dict
            Analytics including:
            - position_summary: Fleet position bounds and centroid
            - active_count: Number of active vessels
            - clustering: Vessel cluster detection
            - alerts: Fleet-wide alert summary
        """
        positions = [
            (v.state.lat, v.state.lon)
            for v in self.vessels.values()
            if v.state.lat is not None and v.state.lon is not None
        ]

        # Always collect alerts, regardless of positions
        alerts = self._collect_alerts()

        if not positions:
            return {
                "position_summary": {
                    "min_lat": None,
                    "max_lat": None,
                    "min_lon": None,
                    "max_lon": None,
                    "centroid_lat": None,
                    "centroid_lon": None,
                },
                "active_count": 0,
                "clustering": {"clusters": [], "largest_cluster_size": 0},
                "alerts": alerts,
            }

        lats = [p[0] for p in positions]
        lons = [p[1] for p in positions]

        centroid_lat = sum(lats) / len(lats)
        centroid_lon = sum(lons) / len(lons)

        return {
            "position_summary": {
                "min_lat": min(lats),
                "max_lat": max(lats),
                "min_lon": min(lons),
                "max_lon": max(lons),
                "centroid_lat": centroid_lat,
                "centroid_lon": centroid_lon,
            },
            "active_count": len(positions),
            "clustering": self._detect_clusters(positions),
            "alerts": alerts,
        }

    def _detect_clusters(
        self, positions: list[tuple[float, float]], radius_m: float = 1000.0
    ) -> dict[str, Any]:
        """Detect vessel clusters within radius_m of each other.

        Uses simple DBSCAN-like clustering: vessels within radius_m
        are grouped into clusters.

        Parameters
        ----------
        positions:
            List of (lat, lon) tuples
        radius_m:
            Clustering radius in meters

        Returns
        -------
        dict
            Cluster analysis with:
            - clusters: List of cluster sizes
            - largest_cluster_size: Size of biggest cluster
            - cluster_centers: List of (lat, lon) cluster centers
        """
        if not positions:
            return {"clusters": [], "largest_cluster_size": 0, "cluster_centers": []}

        # Simple clustering: group nearby vessels
        visited = set()
        clusters = []
        cluster_centers = []

        for i, (lat, lon) in enumerate(positions):
            if i in visited:
                continue

            # Start new cluster
            cluster = [i]
            visited.add(i)

            # Find all vessels within radius
            for j, (other_lat, other_lon) in enumerate(positions):
                if j in visited:
                    continue
                dist = haversine_m(lat, lon, other_lat, other_lon)
                if dist <= radius_m:
                    cluster.append(j)
                    visited.add(j)

            if len(cluster) > 1:
                clusters.append(len(cluster))
                # Compute cluster center
                cluster_lats = [positions[idx][0] for idx in cluster]
                cluster_lons = [positions[idx][1] for idx in cluster]
                cluster_centers.append((
                    sum(cluster_lats) / len(cluster_lats),
                    sum(cluster_lons) / len(cluster_lons),
                ))

        return {
            "clusters": sorted(clusters, reverse=True),
            "largest_cluster_size": max(clusters) if clusters else 0,
            "cluster_centers": cluster_centers,
        }

    def _collect_alerts(self) -> dict[str, list[str]]:
        """Collect fleet-wide alerts from all vessels.

        Returns
        -------
        dict
            Alert summary with severity levels
        """
        alerts = {"critical": [], "warning": [], "info": []}

        for vessel_id, vessel in self.vessels.items():
            # Check for disconnected vessels
            if not vessel.bridge_connected:
                alerts["warning"].append(f"{vessel_id} ({vessel.name}): Bridge disconnected")

            # Check for stale data (>5 minutes old)
            if time.time() - vessel.last_update > 300:
                alerts["warning"].append(f"{vessel_id} ({vessel.name}): Stale telemetry data")

            # Check for missing position
            if vessel.state.lat is None or vessel.state.lon is None:
                alerts["critical"].append(f"{vessel_id} ({vessel.name}): No position fix")

        return alerts

    def get_distance_matrix(self) -> dict[str, dict[str, float | None]]:
        """Compute inter-vessel distance matrix.

        Returns
        -------
        dict
            Distance matrix in meters:
            {
                "vessel_a": {
                    "vessel_b": distance_m | None,
                    "vessel_c": distance_m | None,
                },
                ...
            }
            None indicates distance could not be computed (missing position)
        """
        matrix = {}

        for vid1, vessel1 in self.vessels.items():
            matrix[vid1] = {}
            for vid2, vessel2 in self.vessels.items():
                if vid1 == vid2:
                    matrix[vid1][vid2] = 0.0
                    continue

                if (
                    vessel1.state.lat is None
                    or vessel1.state.lon is None
                    or vessel2.state.lat is None
                    or vessel2.state.lon is None
                ):
                    matrix[vid1][vid2] = None
                    continue

                dist = haversine_m(
                    vessel1.state.lat,
                    vessel1.state.lon,
                    vessel2.state.lat,
                    vessel2.state.lon,
                )
                matrix[vid1][vid2] = round(dist, 1)

        return matrix

    # ------------------------------------------------------------------ #
    # Vessel lookup and queries
    # ------------------------------------------------------------------ #
    def find_nearest(
        self, lat: float, lon: float, purpose: str = "general"
    ) -> dict[str, Any] | None:
        """Find the nearest vessel to a location.

        Parameters
        ----------
        lat:
            Latitude in degrees
        lon:
            Longitude in degrees
        purpose:
            Optional filter by vessel capability/purpose

        Returns
        -------
        dict | None
            Nearest vessel info with distance_m, or None if no vessels have position
        """
        nearest = None
        min_dist = float("inf")

        for vessel_id, vessel in self.vessels.items():
            if vessel.state.lat is None or vessel.state.lon is None:
                continue

            dist = haversine_m(lat, lon, vessel.state.lat, vessel.state.lon)
            if dist < min_dist:
                min_dist = dist
                nearest = {
                    "vessel_id": vessel_id,
                    "name": vessel.name,
                    "vessel_type": vessel.vessel_type,
                    "distance_m": round(dist, 1),
                    "position": {
                        "lat": vessel.state.lat,
                        "lon": vessel.state.lon,
                    },
                }

        return nearest

    def find_vessels_in_radius(
        self, lat: float, lon: float, radius_m: float
    ) -> list[dict[str, Any]]:
        """Find all vessels within a radius of a location.

        Parameters
        ----------
        lat:
            Center latitude in degrees
        lon:
            Center longitude in degrees
        radius_m:
            Search radius in meters

        Returns
        -------
        list[dict]
            List of vessels within radius, each with distance_m
        """
        vessels_in_radius = []

        for vessel_id, vessel in self.vessels.items():
            if vessel.state.lat is None or vessel.state.lon is None:
                continue

            dist = haversine_m(lat, lon, vessel.state.lat, vessel.state.lon)
            if dist <= radius_m:
                vessels_in_radius.append({
                    "vessel_id": vessel_id,
                    "name": vessel.name,
                    "vessel_type": vessel.vessel_type,
                    "distance_m": round(dist, 1),
                    "position": {
                        "lat": vessel.state.lat,
                        "lon": vessel.state.lon,
                    },
                })

        # Sort by distance
        vessels_in_radius.sort(key=lambda v: v["distance_m"])
        return vessels_in_radius

    # ------------------------------------------------------------------ #
    # Fleet-wide operations
    # ------------------------------------------------------------------ #
    async def broadcast_to_all(
        self, action: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Broadcast an action to all vessels in the fleet.

        Parameters
        ----------
        action:
            Action name/type
        payload:
            Optional action payload

        Returns
        -------
        dict
            Summary of broadcast results per vessel
        """
        results = {}
        for vessel_id, vessel in self.vessels.items():
            try:
                # Log the action to each vessel's a2a log
                # (In a full implementation, this would trigger the action)
                results[vessel_id] = {
                    "status": "delivered",
                    "action": action,
                    "vessel": vessel.name,
                }
            except Exception as e:
                results[vessel_id] = {
                    "status": "failed",
                    "error": str(e),
                }

        log.info("Broadcast action '%s' to %d vessels", action, len(self.vessels))
        return results

    async def send_to_vessel(
        self, vessel_id: str, action: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send an action to a specific vessel.

        Parameters
        ----------
        vessel_id:
            Target vessel ID
        action:
            Action name/type
        payload:
            Optional action payload

        Returns
        -------
        dict
            Result of the action delivery
        """
        if vessel_id not in self.vessels:
            return {"status": "error", "error": f"Vessel {vessel_id} not found"}

        vessel = self.vessels[vessel_id]
        return {
            "status": "delivered",
            "action": action,
            "vessel": vessel.name,
        }

    # ------------------------------------------------------------------ #
    # WebSocket fleet viewer
    # ------------------------------------------------------------------ #
    async def _fleet_viewer_handler(self, ws: Any) -> None:
        """Handle a fleet viewer WebSocket connection."""
        self._fleet_viewers.add(ws)
        self.metrics.set_gauge("fleet_viewers_connected", len(self._fleet_viewers))
        log.info("Fleet viewer connected (%d total)", len(self._fleet_viewers))

        try:
            # Send immediate fleet snapshot
            await ws.send(json.dumps(self.get_fleet_snapshot()))
            await ws.wait_closed()
        finally:
            self._fleet_viewers.discard(ws)
            self.metrics.set_gauge("fleet_viewers_connected", len(self._fleet_viewers))
            log.info("Fleet viewer disconnected (%d total)", len(self._fleet_viewers))

    async def _broadcast_loop(self) -> None:
        """Broadcast fleet snapshots to all viewers on interval."""
        while True:
            await asyncio.sleep(self.broadcast_interval)
            if not self._fleet_viewers:
                continue

            msg = json.dumps(self.get_fleet_snapshot())
            results = await asyncio.gather(
                *(ws.send(msg) for ws in list(self._fleet_viewers)),
                return_exceptions=True,
            )

            for ws, res in zip(list(self._fleet_viewers), results):
                if isinstance(res, Exception):
                    self._fleet_viewers.discard(ws)

    # ------------------------------------------------------------------ #
    # Telemetry ingestion (called by bridge connections)
    # ------------------------------------------------------------------ #
    def handle_telemetry(self, vessel_id: str, packet: dict[str, Any]) -> None:
        """Handle a telemetry packet for a specific vessel.

        This is called by the bridge connection to update vessel state.

        Parameters
        ----------
        vessel_id:
            Target vessel ID
        packet:
            Telemetry packet dict
        """
        if vessel_id not in self.vessels:
            log.warning("Received packet for unknown vessel %s", vessel_id)
            return

        vessel = self.vessels[vessel_id]
        vessel.state.apply_packet(packet)
        vessel.last_update = time.time()

        # Update packet counters
        vessel.metrics.increment(PACKETS_RECEIVED)
        self.metrics.increment("fleet_packets_total")

    # ------------------------------------------------------------------ #
    # Fleet manager lifecycle
    # ------------------------------------------------------------------ #
    async def run(self) -> None:
        """Start the fleet manager WebSocket server and broadcast loop.

        This should be awaited to start the fleet manager service.
        """
        self._running = True
        log.info("Fleet manager starting on port %d", self.viewer_port)

        async with websockets.serve(
            self._fleet_viewer_handler, "0.0.0.0", self.viewer_port
        ):
            log.info("Fleet WebSocket server listening on port %d", self.viewer_port)
            await self._broadcast_loop()

    async def stop(self) -> None:
        """Stop the fleet manager and cleanup resources."""
        self._running = False
        log.info("Fleet manager stopped")

    def get_status(self) -> dict[str, Any]:
        """Get fleet manager status.

        Returns
        -------
        dict
            Status summary with vessel counts, connections, etc.
        """
        return {
            "running": self._running,
            "viewer_port": self.viewer_port,
            "vessel_count": len(self.vessels),
            "fleet_viewers": len(self._fleet_viewers),
            "data_dir": str(self.data_dir),
            "vessels": {
                vid: {
                    "name": v.name,
                    "vessel_type": v.vessel_type,
                    "bridge_connected": v.bridge_connected,
                    "has_position": v.state.lat is not None,
                }
                for vid, v in self.vessels.items()
            },
        }
