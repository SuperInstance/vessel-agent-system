"""Tests for the AELMA twin core: VesselState, BathymetryGrid, TwinCore."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from build_kimi.twin.bathymetry import WEEK_NS, BathymetryGrid
from build_kimi.twin.core import TwinCore
from build_kimi.twin.state import VesselState, bearing_deg, haversine_m

T0 = 1_753_478_400_000_000_000  # fixed epoch ns for deterministic tests
SITKA_LAT, SITKA_LON = 57.0531, -135.3300


def pos_packets(lat: float, lon: float, ts: int) -> list[dict]:
    """Build a paired position fix (same timestamp on both components)."""
    return [
        {"timestamp_ns": ts, "source": "nmea0183", "channel": "position.lat",
         "value": lat, "quality": "good"},
        {"timestamp_ns": ts, "source": "nmea0183", "channel": "position.lon",
         "value": lon, "quality": "good"},
    ]


# --------------------------------------------------------------------- #
# Math primitives
# --------------------------------------------------------------------- #

class TestBearing:
    """Great-circle bearing against known compass vectors."""

    @pytest.mark.parametrize("lat2,lon2,expected", [
        (1.0, 0.0, 0.0),     # due north
        (0.0, 1.0, 90.0),    # due east
        (-1.0, 0.0, 180.0),  # due south
        (0.0, -1.0, 270.0),  # due west
    ])
    def test_cardinal(self, lat2, lon2, expected):
        assert bearing_deg(0.0, 0.0, lat2, lon2) == pytest.approx(expected, abs=1e-9)

    def test_northeast_is_45(self):
        assert bearing_deg(0.0, 0.0, 1.0, 1.0) == pytest.approx(45.0, abs=0.1)

    def test_range(self):
        b = bearing_deg(57.0, -135.0, 56.9, -134.8)
        assert 0.0 <= b < 360.0


class TestHaversine:
    """Simplified haversine against the known meters-per-degree values."""

    def test_one_degree_latitude(self):
        assert haversine_m(57.0, -135.0, 58.0, -135.0) == pytest.approx(111000.0)

    def test_one_degree_longitude_scales_with_cos_lat(self):
        d = haversine_m(60.0, -135.0, 60.0, -134.0)
        assert d == pytest.approx(111000.0 * math.cos(math.radians(60.0)))

    def test_diagonal(self):
        # Spec formula: sqrt(dlat^2 + (dlon*cos(lat_mean))^2) * 111000,
        # with lat_mean = 0.5 deg for this leg.
        d = haversine_m(0.0, 0.0, 1.0, 1.0)
        expected = math.sqrt(1.0 + math.cos(math.radians(0.5)) ** 2) * 111000.0
        assert d == pytest.approx(expected)

    def test_zero(self):
        assert haversine_m(57.0, -135.0, 57.0, -135.0) == 0.0


# --------------------------------------------------------------------- #
# VesselState
# --------------------------------------------------------------------- #

class TestVesselState:
    """Packet application, pose derivation, and snapshot shape."""

    def test_apply_and_snapshot(self):
        st = VesselState()
        st.apply_packet({"timestamp_ns": T0, "source": "nmea0183",
                         "channel": "depth_m", "value": 73.2, "quality": "good"})
        for p in pos_packets(SITKA_LAT, SITKA_LON, T0):
            st.apply_packet(p)
        snap = st.snapshot("US-AK-FVEILEEN-51", [500], now_ns=T0)
        assert snap["vessel_id"] == "US-AK-FVEILEEN-51"
        assert snap["timestamp_ns"] == T0
        assert snap["pose"]["lat"] == pytest.approx(SITKA_LAT)
        assert snap["pose"]["lon"] == pytest.approx(SITKA_LON)
        # First fix: no heading/speed yet.
        assert snap["pose"]["heading_deg"] is None
        assert snap["pose"]["speed_kn"] is None
        assert snap["channels"]["depth_m"]["value"] == 73.2
        assert snap["channels"]["position.lat"]["quality"] == "good"

    def test_heading_and_speed_from_fixes(self):
        st = VesselState()
        for p in pos_packets(57.0, -135.0, T0):
            st.apply_packet(p)
        # Steam due north 0.001 deg (~111 m) in 10 s -> 11.1 m/s ~ 21.58 kn.
        for p in pos_packets(57.001, -135.0, T0 + 10_000_000_000):
            st.apply_packet(p)
        assert st.heading_deg == pytest.approx(0.0, abs=1e-6)
        assert st.speed_kn == pytest.approx(11.1 / (1852.0 / 3600.0), rel=1e-6)

    def test_split_fix_does_not_corrupt_heading(self):
        st = VesselState()
        for p in pos_packets(57.0, -135.0, T0):
            st.apply_packet(p)
        # Unpaired lat packet: pose moves, heading/speed untouched.
        st.apply_packet({"timestamp_ns": T0 + 5_000_000_000, "source": "nmea0183",
                         "channel": "position.lat", "value": 57.001})
        assert st.lat == pytest.approx(57.001)
        assert st.heading_deg is None

    def test_dead_reckoning_between_fixes(self):
        st = VesselState()
        for p in pos_packets(57.0, -135.0, T0):
            st.apply_packet(p)
        for p in pos_packets(57.001, -135.0, T0 + 10_000_000_000):
            st.apply_packet(p)
        # 10 s past the last fix at ~11.1 m/s north: another ~111 m.
        snap = st.snapshot("US-AK-FVEILEEN-51", [500], now_ns=T0 + 20_000_000_000)
        assert snap["pose"]["lat"] == pytest.approx(57.002, abs=1e-5)


# --------------------------------------------------------------------- #
# BathymetryGrid
# --------------------------------------------------------------------- #

class TestBathymetryFuse:
    """Fusion, running average, and quantization."""

    def test_single_sample(self):
        g = BathymetryGrid()
        cell = g.fuse(SITKA_LAT, SITKA_LON, 73.2, T0)
        assert cell["depth_m"] == pytest.approx(73.2)
        assert cell["sample_count"] == 1
        assert cell["last_sample_ns"] == T0
        assert cell["source"] == "sounder"
        assert g.total_voxels() == 1

    def test_running_average_same_cell(self):
        g = BathymetryGrid()
        g.fuse(SITKA_LAT, SITKA_LON, 70.0, T0)
        cell = g.fuse(SITKA_LAT, SITKA_LON, 76.0, T0 + 1_000_000_000)
        assert cell["depth_m"] == pytest.approx(73.0)
        assert cell["sample_count"] == 2
        g.fuse(SITKA_LAT, SITKA_LON, 79.0, T0 + 2_000_000_000)
        assert cell["depth_m"] == pytest.approx(75.0)
        assert g.total_voxels() == 1

    def test_source_merge(self):
        g = BathymetryGrid()
        g.fuse(SITKA_LAT, SITKA_LON, 70.0, T0, source="sounder")
        cell = g.fuse(SITKA_LAT, SITKA_LON, 72.0, T0 + 1, source="chart")
        assert cell["source"] == "merged"

    def test_nearby_points_share_cell(self):
        g = BathymetryGrid()
        cell = g.fuse(SITKA_LAT, SITKA_LON, 70.0, T0)
        # ~1 m from the cell center: cannot cross a ~5 m cell edge.
        g.fuse(cell["lat"] + 0.000009, cell["lon"], 72.0, T0 + 1)
        assert g.total_voxels() == 1

    def test_distant_points_new_cell(self):
        g = BathymetryGrid()
        g.fuse(SITKA_LAT, SITKA_LON, 70.0, T0)
        # ~22 m north: next cell over.
        g.fuse(SITKA_LAT + 0.0002, SITKA_LON, 72.0, T0 + 1)
        assert g.total_voxels() == 2


class TestConfidence:
    """Confidence formula: sample count and weekly recency decay."""

    def test_sample_count_ladder(self):
        g = BathymetryGrid()
        cell = None
        for i in range(25):
            cell = g.fuse(SITKA_LAT, SITKA_LON, 70.0, T0)
        assert cell is not None
        cell["sample_count"] = 1
        assert g.confidence(cell, T0) == pytest.approx(0.1)
        cell["sample_count"] = 5
        assert g.confidence(cell, T0) == pytest.approx(0.5)
        cell["sample_count"] = 20
        assert g.confidence(cell, T0) == pytest.approx(0.9)
        cell["sample_count"] = 25  # capped
        assert g.confidence(cell, T0) == pytest.approx(0.9)

    def test_recency_decay(self):
        g = BathymetryGrid()
        cell = g.fuse(SITKA_LAT, SITKA_LON, 70.0, T0)
        cell["sample_count"] = 5
        # One week stale: 0.5 * 0.9; two weeks: 0.5 * 0.81.
        assert g.confidence(cell, T0 + WEEK_NS) == pytest.approx(0.45)
        assert g.confidence(cell, T0 + 2 * WEEK_NS) == pytest.approx(0.405)


class TestViewport:
    """cells_in_radius filtering."""

    def test_radius_filtering(self):
        g = BathymetryGrid()
        g.fuse(SITKA_LAT, SITKA_LON, 70.0, T0)                    # at center
        g.fuse(SITKA_LAT + 0.001, SITKA_LON, 80.0, T0)            # ~111 m north
        g.fuse(SITKA_LAT + 0.01, SITKA_LON, 90.0, T0)             # ~1.1 km north
        cells = g.cells_in_radius(SITKA_LAT, SITKA_LON, 200.0, T0)
        depths = sorted(c[2] for c in cells)
        assert depths == [70.0, 80.0]
        cells = g.cells_in_radius(SITKA_LAT, SITKA_LON, 2000.0, T0)
        assert len(cells) == 3
        for row in cells:
            assert len(row) == 4
            assert 0.0 < row[3] <= 1.0

    def test_empty_grid(self):
        g = BathymetryGrid()
        assert g.cells_in_radius(SITKA_LAT, SITKA_LON, 500.0, T0) == []


class TestPersistence:
    """save/load roundtrip."""

    def test_roundtrip(self, tmp_path):
        g = BathymetryGrid()
        g.fuse(SITKA_LAT, SITKA_LON, 70.0, T0)
        g.fuse(SITKA_LAT, SITKA_LON, 76.0, T0 + 1_000_000_000)
        g.fuse(SITKA_LAT + 0.001, SITKA_LON, 55.5, T0, source="chart")
        path = tmp_path / "bathy.json"
        g.save(path)

        g2 = BathymetryGrid()
        g2.load(path)
        assert g2.total_voxels() == 2
        cells = g2.cells_in_radius(SITKA_LAT, SITKA_LON, 200.0, T0)
        depths = sorted(c[2] for c in cells)
        assert depths == [55.5, 73.0]

    def test_load_missing_file_is_noop(self, tmp_path):
        g = BathymetryGrid()
        g.load(tmp_path / "nope.json")
        assert g.total_voxels() == 0


# --------------------------------------------------------------------- #
# TwinCore integration (no network)
# --------------------------------------------------------------------- #

class TestTwinCore:
    """Packet routing and snapshot assembly."""

    def _core(self, tmp_path) -> TwinCore:
        return TwinCore(bathymetry_path=tmp_path / "bathy.json")

    def test_depth_packet_fuses_at_current_position(self, tmp_path):
        core = self._core(tmp_path)
        for p in pos_packets(SITKA_LAT, SITKA_LON, T0):
            core.handle_packet(p)
        core.handle_packet({"timestamp_ns": T0 + 1, "source": "nmea0183",
                            "channel": "depth_m", "value": 73.2})
        assert core.bathymetry.total_voxels() == 1

    def test_depth_without_position_is_ignored(self, tmp_path):
        core = self._core(tmp_path)
        core.handle_packet({"timestamp_ns": T0, "source": "nmea0183",
                            "channel": "depth_m", "value": 73.2})
        assert core.bathymetry.total_voxels() == 0

    def test_build_snapshot_matches_schema_shape(self, tmp_path):
        core = self._core(tmp_path)
        for p in pos_packets(SITKA_LAT, SITKA_LON, T0):
            core.handle_packet(p)
        core.handle_packet({"timestamp_ns": T0 + 1, "source": "simulator",
                            "channel": "depth_m", "value": 73.2})
        snap = core.build_snapshot(now_ns=T0 + 2)
        assert set(snap) >= {"timestamp_ns", "vessel_id", "pose", "channels", "bathymetry"}
        assert snap["vessel_id"] == "US-AK-FVEILEEN-51"
        bathy = snap["bathymetry"]
        assert bathy["voxel_count"] == 1
        assert bathy["viewport_center"] == {"lat": pytest.approx(SITKA_LAT),
                                            "lon": pytest.approx(SITKA_LON)}
        assert bathy["viewport_radius_m"] == 500.0
        assert len(bathy["cells"]) == 1
        lat, lon, depth, conf = bathy["cells"][0]
        assert depth == pytest.approx(73.2)
        assert conf == pytest.approx(0.1, abs=1e-3)
