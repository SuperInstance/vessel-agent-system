"""Tests for fleet management system."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets

from twin.fleet_manager import FleetManager, VesselInstance


@pytest.fixture
def temp_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def fleet_config():
    """Sample fleet configuration."""
    return {
        "vessel1": {
            "bridge_url": "ws://localhost:8000",
            "viewer_port": 8090,
            "name": "F/V Pioneer",
            "vessel_type": "fishing",
            "bathymetry_path": "bathymetry_v1.json",
        },
        "vessel2": {
            "bridge_url": "ws://localhost:8001",
            "viewer_port": 8091,
            "name": "F/V Explorer",
            "vessel_type": "fishing",
            "bathymetry_path": "bathymetry_v2.json",
        },
        "vessel3": {
            "bridge_url": "ws://localhost:8002",
            "viewer_port": 8092,
            "name": "R/V Surveyor",
            "vessel_type": "research",
            "bathymetry_path": "bathymetry_v3.json",
        },
    }


@pytest.fixture
def fleet_manager(temp_dir):
    """Create a fleet manager instance."""
    return FleetManager(
        viewer_port=8099,
        broadcast_interval=0.1,
        data_dir=temp_dir / "fleet",
    )


class TestVesselInstance:
    """Test VesselInstance container."""

    def test_init(self, temp_dir):
        """Test vessel instance initialization."""
        config = {
            "bridge_url": "ws://localhost:8000",
            "viewer_port": 8090,
            "name": "Test Vessel",
            "vessel_type": "fishing",
        }

        vessel = VesselInstance("US-AK-TEST-01", config, temp_dir)

        assert vessel.vessel_id == "US-AK-TEST-01"
        assert vessel.name == "Test Vessel"
        assert vessel.vessel_type == "fishing"
        assert vessel.data_dir == temp_dir / "US-AK-TEST-01"
        assert vessel.data_dir.exists()

    def test_default_values(self, temp_dir):
        """Test default configuration values."""
        config = {"bridge_url": "ws://localhost:8000"}

        vessel = VesselInstance("US-AK-TEST-02", config, temp_dir)

        assert vessel.name == "US-AK-TEST-02"  # defaults to vessel_id
        assert vessel.vessel_type == "unknown"


class TestFleetManager:
    """Test FleetManager core functionality."""

    def test_init(self, temp_dir):
        """Test fleet manager initialization."""
        manager = FleetManager(data_dir=temp_dir / "fleet")

        assert manager.viewer_port == 8092  # default
        assert manager.broadcast_interval == 1.0  # default
        assert manager.data_dir == temp_dir / "fleet"
        assert manager.data_dir.exists()
        assert len(manager.vessels) == 0

    def test_register_vessel(self, fleet_manager, fleet_config):
        """Test vessel registration."""
        config = fleet_config["vessel1"]
        vessel = fleet_manager.register_vessel("vessel1", config)

        assert isinstance(vessel, VesselInstance)
        assert vessel.vessel_id == "vessel1"
        assert "vessel1" in fleet_manager.vessels
        assert len(fleet_manager.vessels) == 1

    def test_register_duplicate_raises(self, fleet_manager, fleet_config):
        """Test that duplicate registration raises error."""
        config = fleet_config["vessel1"]
        fleet_manager.register_vessel("vessel1", config)

        with pytest.raises(ValueError, match="already registered"):
            fleet_manager.register_vessel("vessel1", config)

    def test_unregister_vessel(self, fleet_manager, fleet_config):
        """Test vessel unregistration."""
        config = fleet_config["vessel1"]
        fleet_manager.register_vessel("vessel1", config)

        fleet_manager.unregister_vessel("vessel1")

        assert "vessel1" not in fleet_manager.vessels
        assert len(fleet_manager.vessels) == 0

    def test_unregister_nonexistent_raises(self, fleet_manager):
        """Test that unregistering nonexistent vessel raises error."""
        with pytest.raises(KeyError, match="not found"):
            fleet_manager.unregister_vessel("nonexistent")

    def test_get_vessel(self, fleet_manager, fleet_config):
        """Test getting a vessel instance."""
        config = fleet_config["vessel1"]
        registered = fleet_manager.register_vessel("vessel1", config)

        retrieved = fleet_manager.get_vessel("vessel1")

        assert retrieved is registered
        assert retrieved.vessel_id == "vessel1"

    def test_get_nonexistent_vessel_raises(self, fleet_manager):
        """Test that getting nonexistent vessel raises error."""
        with pytest.raises(KeyError, match="not found"):
            fleet_manager.get_vessel("nonexistent")

    def test_list_vessels(self, fleet_manager, fleet_config):
        """Test listing all vessels."""
        fleet_manager.register_vessel("vessel1", fleet_config["vessel1"])
        fleet_manager.register_vessel("vessel2", fleet_config["vessel2"])
        fleet_manager.register_vessel("vessel3", fleet_config["vessel3"])

        vessel_ids = fleet_manager.list_vessels()

        assert set(vessel_ids) == {"vessel1", "vessel2", "vessel3"}


class TestTelemetryHandling:
    """Test telemetry packet handling."""

    def test_handle_telemetry_unknown_vessel(self, fleet_manager):
        """Test handling telemetry for unknown vessel logs warning."""
        packet = {
            "channel": "position.lat",
            "value": 59.5,
            "timestamp_ns": 1234567890000000000,
        }

        # Should not raise, just log warning
        fleet_manager.handle_telemetry("unknown", packet)

    def test_handle_telemetry_updates_state(self, fleet_manager, fleet_config):
        """Test that telemetry updates vessel state."""
        config = fleet_config["vessel1"]
        fleet_manager.register_vessel("vessel1", config)

        # Send position update
        packet = {
            "channel": "position.lat",
            "value": 59.5,
            "timestamp_ns": 1234567890000000000,
        }
        fleet_manager.handle_telemetry("vessel1", packet)

        vessel = fleet_manager.get_vessel("vessel1")
        assert vessel.state.lat == 59.5
        assert vessel.last_update > 0


class TestStateAccess:
    """Test state access methods."""

    def test_get_vessel_state(self, fleet_manager, fleet_config):
        """Test getting vessel state snapshot."""
        config = fleet_config["vessel1"]
        fleet_manager.register_vessel("vessel1", config)

        # Update state
        vessel = fleet_manager.get_vessel("vessel1")
        vessel.state.lat = 59.5
        vessel.state.lon = -152.3

        state = fleet_manager.get_vessel_state("vessel1")

        assert state is not None
        assert state["vessel_id"] == "vessel1"
        assert state["name"] == "F/V Pioneer"
        assert state["pose"]["lat"] == 59.5
        assert state["pose"]["lon"] == -152.3

    def test_get_vessel_state_nonexistent(self, fleet_manager):
        """Test getting state for nonexistent vessel returns None."""
        state = fleet_manager.get_vessel_state("nonexistent")
        assert state is None

    def test_get_all_positions(self, fleet_manager, fleet_config):
        """Test getting all vessel positions."""
        fleet_manager.register_vessel("vessel1", fleet_config["vessel1"])
        fleet_manager.register_vessel("vessel2", fleet_config["vessel2"])

        # Set positions
        v1 = fleet_manager.get_vessel("vessel1")
        v1.state.lat = 59.5
        v1.state.lon = -152.3

        v2 = fleet_manager.get_vessel("vessel2")
        v2.state.lat = 60.0
        v2.state.lon = -151.0

        positions = fleet_manager.get_all_positions()

        assert len(positions) == 2
        assert positions["vessel1"]["lat"] == 59.5
        assert positions["vessel2"]["lat"] == 60.0

    def test_get_fleet_snapshot(self, fleet_manager, fleet_config):
        """Test comprehensive fleet snapshot."""
        fleet_manager.register_vessel("vessel1", fleet_config["vessel1"])
        fleet_manager.register_vessel("vessel2", fleet_config["vessel2"])

        # Set positions
        v1 = fleet_manager.get_vessel("vessel1")
        v1.state.lat = 59.5
        v1.state.lon = -152.3

        snapshot = fleet_manager.get_fleet_snapshot()

        assert "timestamp_ns" in snapshot
        assert snapshot["vessel_count"] == 2
        assert "vessel1" in snapshot["vessels"]
        assert "analytics" in snapshot


class TestFleetAnalytics:
    """Test fleet-level analytics."""

    def test_position_summary_empty_fleet(self, fleet_manager):
        """Test position summary with no vessels."""
        snapshot = fleet_manager.get_fleet_snapshot()
        analytics = snapshot["analytics"]
        summary = analytics["position_summary"]

        assert summary["min_lat"] is None
        assert summary["centroid_lat"] is None

    def test_position_summary_with_positions(self, fleet_manager, fleet_config):
        """Test position summary calculation."""
        fleet_manager.register_vessel("vessel1", fleet_config["vessel1"])
        fleet_manager.register_vessel("vessel2", fleet_config["vessel2"])

        # Set positions
        v1 = fleet_manager.get_vessel("vessel1")
        v1.state.lat = 59.0
        v1.state.lon = -152.0

        v2 = fleet_manager.get_vessel("vessel2")
        v2.state.lat = 60.0
        v2.state.lon = -151.0

        snapshot = fleet_manager.get_fleet_snapshot()
        summary = snapshot["analytics"]["position_summary"]

        assert summary["min_lat"] == 59.0
        assert summary["max_lat"] == 60.0
        assert summary["centroid_lat"] == 59.5
        assert summary["centroid_lon"] == -151.5

    def test_cluster_detection(self, fleet_manager, fleet_config):
        """Test vessel cluster detection."""
        # Register 3 vessels close together
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])
        fleet_manager.register_vessel("v3", fleet_config["vessel3"])

        # Position them within 500m of each other
        v1 = fleet_manager.get_vessel("v1")
        v1.state.lat = 59.0
        v1.state.lon = -152.0

        v2 = fleet_manager.get_vessel("v2")
        v2.state.lat = 59.004  # ~500m north
        v2.state.lon = -152.0

        v3 = fleet_manager.get_vessel("v3")
        v3.state.lat = 59.002
        v3.state.lon = -152.002

        snapshot = fleet_manager.get_fleet_snapshot()
        clustering = snapshot["analytics"]["clustering"]

        assert clustering["largest_cluster_size"] >= 2
        assert len(clustering["clusters"]) > 0

    def test_alert_collection(self, fleet_manager, fleet_config):
        """Test fleet alert collection."""
        fleet_manager.register_vessel("vessel1", fleet_config["vessel1"])

        vessel = fleet_manager.get_vessel("vessel1")
        vessel.bridge_connected = False
        # No position set

        snapshot = fleet_manager.get_fleet_snapshot()
        alerts = snapshot["analytics"]["alerts"]

        assert len(alerts["critical"]) > 0  # No position
        assert len(alerts["warning"]) > 0  # Disconnected


class TestDistanceMatrix:
    """Test inter-vessel distance calculations."""

    def test_distance_matrix(self, fleet_manager, fleet_config):
        """Test distance matrix computation."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])

        v1 = fleet_manager.get_vessel("v1")
        v1.state.lat = 59.0
        v1.state.lon = -152.0

        v2 = fleet_manager.get_vessel("v2")
        v2.state.lat = 60.0
        v2.state.lon = -151.0

        matrix = fleet_manager.get_distance_matrix()

        assert "v1" in matrix
        assert "v2" in matrix
        assert matrix["v1"]["v1"] == 0.0
        assert matrix["v2"]["v2"] == 0.0
        assert matrix["v1"]["v2"] > 100000  # ~111km per degree
        assert matrix["v2"]["v1"] == matrix["v1"]["v2"]

    def test_distance_matrix_missing_position(self, fleet_manager, fleet_config):
        """Test distance matrix with missing positions."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])

        # v1 has position, v2 does not
        v1 = fleet_manager.get_vessel("v1")
        v1.state.lat = 59.0
        v1.state.lon = -152.0

        matrix = fleet_manager.get_distance_matrix()

        assert matrix["v1"]["v2"] is None
        assert matrix["v2"]["v1"] is None


class TestVesselLookup:
    """Test vessel lookup and search methods."""

    def test_find_nearest(self, fleet_manager, fleet_config):
        """Test finding nearest vessel to location."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])

        v1 = fleet_manager.get_vessel("v1")
        v1.state.lat = 59.0
        v1.state.lon = -152.0

        v2 = fleet_manager.get_vessel("v2")
        v2.state.lat = 60.0
        v2.state.lon = -151.0

        # Query near v1
        nearest = fleet_manager.find_nearest(59.001, -152.0)

        assert nearest is not None
        assert nearest["vessel_id"] == "v1"
        assert nearest["distance_m"] < 200  # ~111m

    def test_find_nearest_no_positions(self, fleet_manager, fleet_config):
        """Test finding nearest when no vessels have position."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        # No position set

        nearest = fleet_manager.find_nearest(59.0, -152.0)

        assert nearest is None

    def test_find_vessels_in_radius(self, fleet_manager, fleet_config):
        """Test finding vessels within radius."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])

        v1 = fleet_manager.get_vessel("v1")
        v1.state.lat = 59.0
        v1.state.lon = -152.0

        v2 = fleet_manager.get_vessel("v2")
        v2.state.lat = 60.0
        v2.state.lon = -151.0

        # 1km radius around v1
        vessels = fleet_manager.find_vessels_in_radius(59.0, -152.0, 1000)

        assert len(vessels) == 1
        assert vessels[0]["vessel_id"] == "v1"
        assert vessels[0]["distance_m"] < 100

    def test_find_vessels_in_radius_sorted(self, fleet_manager, fleet_config):
        """Test that radius search returns vessels sorted by distance."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])

        v1 = fleet_manager.get_vessel("v1")
        v1.state.lat = 59.0
        v1.state.lon = -152.0

        v2 = fleet_manager.get_vessel("v2")
        v2.state.lat = 59.01
        v2.state.lon = -152.0

        vessels = fleet_manager.find_vessels_in_radius(59.0, -152.0, 5000)

        assert len(vessels) == 2
        assert vessels[0]["distance_m"] < vessels[1]["distance_m"]


class TestFleetOperations:
    """Test fleet-wide operations."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all(self, fleet_manager, fleet_config):
        """Test broadcasting action to all vessels."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])

        results = await fleet_manager.broadcast_to_all(
            "return_to_port", {"port": "kodiak"}
        )

        assert len(results) == 2
        assert "v1" in results
        assert "v2" in results
        assert results["v1"]["status"] == "delivered"
        assert results["v1"]["action"] == "return_to_port"

    @pytest.mark.asyncio
    async def test_send_to_vessel(self, fleet_manager, fleet_config):
        """Test sending action to specific vessel."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])

        result = await fleet_manager.send_to_vessel(
            "v1", "set_watch", {"watch_station": "port"}
        )

        assert result["status"] == "delivered"
        assert result["vessel"] == "F/V Pioneer"

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_vessel(self, fleet_manager):
        """Test sending action to nonexistent vessel."""
        result = await fleet_manager.send_to_vessel(
            "nonexistent", "set_watch", {}
        )

        assert result["status"] == "error"


class TestWebSocketAPI:
    """Test WebSocket fleet viewer API."""

    @pytest.mark.asyncio
    async def test_fleet_viewer_handler(self, fleet_manager, fleet_config):
        """Test fleet viewer WebSocket handler."""
        # Register vessels
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        v1 = fleet_manager.get_vessel("v1")
        v1.state.lat = 59.0
        v1.state.lon = -152.0

        # Mock WebSocket
        ws = AsyncMock()
        ws.wait_closed = AsyncMock()
        ws.send = AsyncMock()

        # Handle connection
        await fleet_manager._fleet_viewer_handler(ws)

        # Verify snapshot sent
        assert ws.send.called
        snapshot = json.loads(ws.send.call_args[0][0])
        assert snapshot["vessel_count"] == 1
        assert "v1" in snapshot["vessels"]

    @pytest.mark.asyncio
    async def test_broadcast_loop(self, fleet_manager, fleet_config):
        """Test broadcast loop sends snapshots to viewers."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])

        # Mock viewers
        ws1 = AsyncMock()
        ws1.send = AsyncMock()
        ws2 = AsyncMock()
        ws2.send = AsyncMock()

        fleet_manager._fleet_viewers = {ws1, ws2}

        # Run one broadcast iteration
        task = asyncio.create_task(fleet_manager._broadcast_loop())
        await asyncio.sleep(0.15)  # Wait for one broadcast (0.1s interval)
        task.cancel()

        # Verify both viewers received snapshot
        assert ws1.send.called
        assert ws2.send.called


class TestStatusAndLifecycle:
    """Test status and lifecycle methods."""

    def test_get_status(self, fleet_manager, fleet_config):
        """Test getting fleet manager status."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])

        v1 = fleet_manager.get_vessel("v1")
        v1.state.lat = 59.0
        v1.bridge_connected = True

        status = fleet_manager.get_status()

        assert status["viewer_port"] == 8099
        assert status["vessel_count"] == 2
        assert status["fleet_viewers"] == 0
        assert "v1" in status["vessels"]
        assert status["vessels"]["v1"]["bridge_connected"] is True
        assert status["vessels"]["v2"]["bridge_connected"] is False

    @pytest.mark.asyncio
    async def test_lifecycle(self, fleet_manager):
        """Test fleet manager lifecycle."""
        assert not fleet_manager._running

        # Start
        task = asyncio.create_task(fleet_manager.run())
        await asyncio.sleep(0.1)

        assert fleet_manager._running

        # Stop
        await fleet_manager.stop()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass


class TestIsolatedState:
    """Test that vessels have isolated state."""

    def test_independent_telemetry(self, fleet_manager, fleet_config):
        """Test that telemetry for one vessel doesn't affect others."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])

        # Update v1
        packet1 = {
            "channel": "position.lat",
            "value": 59.0,
            "timestamp_ns": 1234567890000000000,
        }
        fleet_manager.handle_telemetry("v1", packet1)

        # Update v2
        packet2 = {
            "channel": "position.lat",
            "value": 60.0,
            "timestamp_ns": 1234567890000000000,
        }
        fleet_manager.handle_telemetry("v2", packet2)

        v1 = fleet_manager.get_vessel("v1")
        v2 = fleet_manager.get_vessel("v2")

        assert v1.state.lat == 59.0
        assert v2.state.lat == 60.0

    def test_independent_data_dirs(self, fleet_manager, fleet_config, temp_dir):
        """Test that each vessel has its own data directory."""
        fleet_manager.register_vessel("v1", fleet_config["vessel1"])
        fleet_manager.register_vessel("v2", fleet_config["vessel2"])

        v1 = fleet_manager.get_vessel("v1")
        v2 = fleet_manager.get_vessel("v2")

        assert v1.data_dir != v2.data_dir
        assert v1.data_dir.name == "v1"
        assert v2.data_dir.name == "v2"
        assert v1.data_dir.is_dir()
        assert v2.data_dir.is_dir()
