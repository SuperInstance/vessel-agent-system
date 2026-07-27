"""Tests for the AELMA twin core (build_claude).

Covers VesselState apply+snapshot, bearing computation, haversine distance,
bathymetry fusion (single + multiple samples, running average), cell
quantisation, viewport radius filtering, confidence formula (sample count
+ recency), and persistence save/load roundtrip.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time

import pytest

from build_claude.twin.state import (
    VesselState,
    bearing_deg,
    haversine_m,
    mps_to_knots,
)
from build_claude.twin.bathymetry import (
    BathymetryGrid,
    quantise_cell,
    cell_center,
)
from build_claude.twin.core import TwinCore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_packet(
    channel: str,
    value: float | str | bool | None,
    ts_ns: int,
    source: str = "nmea0183",
    quality: str = "good",
) -> dict:
    """Build a minimal TelemetryPacket dict."""
    return {
        "timestamp_ns": ts_ns,
        "source": source,
        "channel": channel,
        "value": value,
        "quality": quality,
    }


# Reference timestamp: 2025-07-25T12:00:00Z
_T0 = 1_753_478_400_000_000_000


# ---------------------------------------------------------------------------
# 1. State apply + snapshot
# ---------------------------------------------------------------------------

class TestVesselStateApplySnapshot:
    """VesselState should store per-channel readings and emit snapshots."""

    def test_apply_stores_channel(self):
        """A non-position channel should be stored verbatim."""
        vs = VesselState()
        vs.apply_packet(_make_packet("depth_m", 73.2, _T0))
        assert vs.channels["depth_m"]["value"] == 73.2
        assert vs.channels["depth_m"]["timestamp_ns"] == _T0
        assert vs.channels["depth_m"]["quality"] == "good"

    def test_apply_updates_quality(self):
        """A second packet on the same channel should overwrite."""
        vs = VesselState()
        vs.apply_packet(_make_packet("sea_temp_c", 9.5, _T0, quality="good"))
        vs.apply_packet(_make_packet("sea_temp_c", 9.8, _T0 + 1_000_000_000, quality="fair"))
        assert vs.channels["sea_temp_c"]["value"] == 9.8
        assert vs.channels["sea_temp_c"]["quality"] == "fair"

    def test_snapshot_has_required_fields(self):
        """Snapshot must match the VesselStateSnapshot schema top-level keys."""
        vs = VesselState()
        vs.apply_packet(_make_packet("position.lat", 56.80134, _T0))
        vs.apply_packet(_make_packet("position.lon", -135.30278, _T0))
        snap = vs.snapshot("US-AK-FVEILEEN-51")
        assert snap["vessel_id"] == "US-AK-FVEILEEN-51"
        assert "timestamp_ns" in snap
        assert "pose" in snap
        assert "channels" in snap
        assert "lat" in snap["pose"]
        assert "lon" in snap["pose"]

    def test_snapshot_channels_contain_readings(self):
        """Snapshot channels should reflect applied packets."""
        vs = VesselState()
        vs.apply_packet(_make_packet("depth_m", 73.2, _T0))
        vs.apply_packet(_make_packet("wind_kts", 8.0, _T0))
        snap = vs.snapshot("US-AK-FVEILEEN-51")
        assert "depth_m" in snap["channels"]
        assert snap["channels"]["depth_m"]["value"] == 73.2
        assert "wind_kts" in snap["channels"]
        assert snap["channels"]["wind_kts"]["value"] == 8.0

    def test_snapshot_with_bathymetry_viewport(self):
        """Snapshot with viewport should include bathymetry section."""
        vs = VesselState()
        vs.apply_packet(_make_packet("position.lat", 56.80134, _T0))
        vs.apply_packet(_make_packet("position.lon", -135.30278, _T0))

        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 73.2, _T0)

        snap = vs.snapshot(
            "US-AK-FVEILEEN-51",
            viewport=[56.80134, -135.30278, 500.0],
            bathymetry=grid,
        )
        assert "bathymetry" in snap
        assert snap["bathymetry"]["voxel_count"] == 1
        assert snap["bathymetry"]["viewport_radius_m"] == 500.0
        assert len(snap["bathymetry"]["cells"]) == 1


# ---------------------------------------------------------------------------
# 2. Bearing computation (known vectors)
# ---------------------------------------------------------------------------

class TestBearing:
    """Great-circle bearing computation against known vectors."""

    def test_due_east(self):
        """Bearing from a point to one directly east should be ~90 degrees."""
        # At equator, moving east
        result = bearing_deg(0.0, 0.0, 0.0, 0.01)
        assert abs(result - 90.0) < 0.5

    def test_due_north(self):
        """Bearing directly north should be 0 degrees."""
        result = bearing_deg(0.0, 0.0, 0.01, 0.0)
        assert abs(result - 0.0) < 0.5

    def test_due_south(self):
        """Bearing directly south should be 180 degrees."""
        result = bearing_deg(0.01, 0.0, 0.0, 0.0)
        assert abs(result - 180.0) < 0.5

    def test_due_west(self):
        """Bearing directly west should be 270 degrees."""
        result = bearing_deg(0.0, 0.01, 0.0, 0.0)
        assert abs(result - 270.0) < 0.5

    def test_northeast(self):
        """Bearing northeast should be ~45 degrees."""
        result = bearing_deg(0.0, 0.0, 0.01, 0.01)
        assert abs(result - 45.0) < 1.0

    def test_range_0_to_360(self):
        """Bearing should always be in [0, 360)."""
        result = bearing_deg(45.0, -150.0, 60.0, -130.0)
        assert 0.0 <= result < 360.0

    def test_from_position_packets(self):
        """Applying two position fixes should compute heading."""
        vs = VesselState()
        # First fix: 56.80 N, 135.30 W
        vs.apply_packet(_make_packet("position.lat", 56.80134, _T0))
        vs.apply_packet(_make_packet("position.lon", -135.30278, _T0))
        assert vs.heading_deg is None  # No previous fix yet

        # Second fix: ~100m east and ~100m north, 10 seconds later
        # 100m north = ~0.0009 degrees lat
        # 100m east at lat 56.8 = ~0.00165 degrees lon
        dt_ns = 10 * 1_000_000_000
        vs.apply_packet(_make_packet("position.lat", 56.80224, _T0 + dt_ns))
        vs.apply_packet(_make_packet("position.lon", -135.30113, _T0 + dt_ns))

        assert vs.heading_deg is not None
        # Moving NE: bearing should be between 20 and 70 degrees
        assert 20.0 < vs.heading_deg < 70.0


# ---------------------------------------------------------------------------
# 3. Haversine distance vs known formula
# ---------------------------------------------------------------------------

class TestHaversine:
    """Haversine distance validation."""

    def test_zero_distance(self):
        """Same point should give zero distance."""
        assert haversine_m(56.8, -135.3, 56.8, -135.3) == 0.0

    def test_known_short_distance(self):
        """100m north should be ~100m."""
        # 0.0009 degrees lat ~ 100m
        d = haversine_m(56.80134, -135.30278, 56.80224, -135.30278)
        assert abs(d - 100.0) < 5.0

    def test_known_east_west(self):
        """100m east at ~57N should be ~100m."""
        # At lat 56.8: cos(56.8 deg) ~ 0.547
        # 100m east = 100 / (111000 * cos(56.8 deg)) = 100 / 60683 ~ 0.001648 deg
        d = haversine_m(56.80134, -135.30278, 56.80134, -135.30113)
        assert abs(d - 100.0) < 5.0

    def test_diagonal_distance(self):
        """Moving 100m N + 100m E should give ~141m."""
        d = haversine_m(56.80134, -135.30278, 56.80224, -135.30113)
        assert abs(d - 141.42) < 10.0


# ---------------------------------------------------------------------------
# 4. Speed computation from position fixes
# ---------------------------------------------------------------------------

class TestSpeedComputation:
    """Speed should be computed from haversine distance / dt."""

    def test_speed_from_two_fixes(self):
        """Moving 100m in 10s should give ~19.4 knots."""
        vs = VesselState()
        vs.apply_packet(_make_packet("position.lat", 56.80134, _T0))
        vs.apply_packet(_make_packet("position.lon", -135.30278, _T0))

        dt_ns = 10 * 1_000_000_000
        vs.apply_packet(_make_packet("position.lat", 56.80224, _T0 + dt_ns))
        vs.apply_packet(_make_packet("position.lon", -135.30278, _T0 + dt_ns))

        assert vs.speed_kn is not None
        # 100m / 10s = 10 m/s = 19.44 knots
        assert abs(vs.speed_kn - 19.44) < 1.0


# ---------------------------------------------------------------------------
# 5. Bathymetry fusion
# ---------------------------------------------------------------------------

class TestBathymetryFusion:
    """BathymetryGrid fusion: single sample, multiple samples, running average."""

    def test_single_sample(self):
        """A single fuse call should create one cell with correct depth."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 73.2, _T0)
        assert grid.total_voxels() == 1

    def test_multiple_samples_same_cell(self):
        """Multiple samples in the same cell should average correctly."""
        grid = BathymetryGrid()
        # These should quantise to the same ~10m cell
        grid.fuse(56.80134, -135.30278, 70.0, _T0)
        grid.fuse(56.80134, -135.30278, 80.0, _T0 + 1_000_000_000)
        assert grid.total_voxels() == 1

        cells = grid.cells_in_radius(56.80134, -135.30278, 50.0)
        assert len(cells) == 1
        # Running average: 70 -> 75
        assert abs(cells[0][2] - 75.0) < 0.01

    def test_running_average_three_samples(self):
        """Three samples: 60, 80, 90 -> running avg should be correct."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 60.0, _T0)
        grid.fuse(56.80134, -135.30278, 80.0, _T0 + 1)
        grid.fuse(56.80134, -135.30278, 90.0, _T0 + 2)
        cells = grid.cells_in_radius(56.80134, -135.30278, 50.0)
        assert len(cells) == 1
        # Running average: 60 -> 70 -> 76.667
        assert abs(cells[0][2] - 76.667) < 0.1

    def test_different_cells(self):
        """Points far enough apart should create separate cells."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 70.0, _T0)
        # ~500m away -- definitely a different cell
        grid.fuse(56.80580, -135.29800, 80.0, _T0 + 1)
        assert grid.total_voxels() == 2


# ---------------------------------------------------------------------------
# 6. Cell quantisation
# ---------------------------------------------------------------------------

class TestCellQuantisation:
    """Nearby points should map to the same cell; far points to different cells."""

    def test_nearby_points_same_cell(self):
        """Points within ~5m should quantise to the same cell."""
        c1 = quantise_cell(56.80134, -135.30278)
        c2 = quantise_cell(56.80135, -135.30279)
        assert c1 == c2

    def test_far_points_different_cell(self):
        """Points ~50m apart should quantise to different cells."""
        c1 = quantise_cell(56.80134, -135.30278)
        # 50m north: ~0.00045 degrees lat
        c2 = quantise_cell(56.80179, -135.30278)
        assert c1 != c2

    def test_cell_center_roundtrip(self):
        """Cell center should be close to original position."""
        lat, lon = 56.80134, -135.30278
        clat, clon = quantise_cell(lat, lon)
        center_lat, center_lon = cell_center(clat, clon, ref_lat=lat)
        # Center should be within one cell size (~10m) of original
        d = haversine_m(lat, lon, center_lat, center_lon)
        assert d < 15.0  # within ~15m (half a cell + rounding)


# ---------------------------------------------------------------------------
# 7. Viewport radius filtering
# ---------------------------------------------------------------------------

class TestViewportRadius:
    """cells_in_radius should filter by distance."""

    def test_only_nearby_cells_returned(self):
        """Only cells within the radius should be returned."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 70.0, _T0)
        grid.fuse(56.80580, -135.29800, 80.0, _T0 + 1)  # ~500m away

        # Small radius: only the first cell
        near = grid.cells_in_radius(56.80134, -135.30278, 50.0)
        assert len(near) == 1

        # Large radius: both cells
        far = grid.cells_in_radius(56.80134, -135.30278, 1000.0)
        assert len(far) == 2

    def test_empty_grid_returns_empty(self):
        """An empty grid should return an empty list."""
        grid = BathymetryGrid()
        assert grid.cells_in_radius(0.0, 0.0, 1000.0) == []


# ---------------------------------------------------------------------------
# 8. Confidence formula
# ---------------------------------------------------------------------------

class TestConfidence:
    """Confidence should follow: min(0.1 * count, 0.9) with recency decay."""

    def test_single_sample_confidence(self):
        """One sample should give 0.1 confidence (no decay)."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 70.0, _T0)
        cells = grid.cells_in_radius(56.80134, -135.30278, 50.0)
        assert len(cells) == 1
        assert abs(cells[0][3] - 0.1) < 0.001

    def test_five_samples_confidence(self):
        """Five samples should give 0.5 confidence."""
        grid = BathymetryGrid()
        for i in range(5):
            grid.fuse(56.80134, -135.30278, 70.0 + i, _T0 + i * 1_000_000_000)
        cells = grid.cells_in_radius(56.80134, -135.30278, 50.0)
        assert len(cells) == 1
        assert abs(cells[0][3] - 0.5) < 0.001

    def test_twenty_plus_samples_confidence(self):
        """Twenty or more samples should cap at 0.9 confidence."""
        grid = BathymetryGrid()
        for i in range(25):
            grid.fuse(56.80134, -135.30278, 70.0 + i, _T0 + i * 1_000_000_000)
        cells = grid.cells_in_radius(56.80134, -135.30278, 50.0)
        assert len(cells) == 1
        assert abs(cells[0][3] - 0.9) < 0.001

    def test_recency_decay(self):
        """Confidence should drop 10% per week of age."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 70.0, _T0)

        # One week later: 10% decay
        week_ns = 7 * 24 * 3600 * 1_000_000_000
        cells = grid.cells_in_radius(
            56.80134, -135.30278, 50.0, now_ns=_T0 + week_ns
        )
        assert len(cells) == 1
        # 0.1 * (1 - 0.1) = 0.09
        assert abs(cells[0][3] - 0.09) < 0.002

    def test_recency_decay_two_weeks(self):
        """Two weeks old: 20% decay."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 70.0, _T0)
        grid.fuse(56.80134, -135.30278, 70.0, _T0 + 1)  # 2 samples -> 0.2

        week_ns = 7 * 24 * 3600 * 1_000_000_000
        cells = grid.cells_in_radius(
            56.80134, -135.30278, 50.0, now_ns=_T0 + 2 * week_ns
        )
        assert len(cells) == 1
        # base = 0.2, decay = 1 - 0.2 = 0.8, conf = 0.16
        assert abs(cells[0][3] - 0.16) < 0.002

    def test_recency_decay_zero_after_10_weeks(self):
        """After 10 weeks, confidence should be 0."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 70.0, _T0)

        week_ns = 7 * 24 * 3600 * 1_000_000_000
        cells = grid.cells_in_radius(
            56.80134, -135.30278, 50.0, now_ns=_T0 + 10 * week_ns
        )
        assert len(cells) == 1
        assert cells[0][3] == 0.0


# ---------------------------------------------------------------------------
# 9. Persistence save/load roundtrip
# ---------------------------------------------------------------------------

class TestPersistence:
    """BathymetryGrid save/load roundtrip."""

    def test_save_load_roundtrip(self):
        """Saving and loading should preserve all cell data."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 73.2, _T0)
        grid.fuse(56.80134, -135.30278, 76.8, _T0 + 1_000_000_000)
        grid.fuse(56.80580, -135.29800, 80.0, _T0 + 2_000_000_000)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            path = f.name

        try:
            grid.save(path)

            loaded = BathymetryGrid()
            loaded.load(path)

            assert loaded.total_voxels() == grid.total_voxels()
            assert loaded.total_voxels() == 2

            original_cells = sorted(
                grid.cells_in_radius(56.80134, -135.30278, 1000.0),
                key=lambda c: (c[0], c[1]),
            )
            loaded_cells = sorted(
                loaded.cells_in_radius(56.80134, -135.30278, 1000.0),
                key=lambda c: (c[0], c[1]),
            )
            assert len(original_cells) == len(loaded_cells)
            for orig, load in zip(original_cells, loaded_cells):
                assert abs(orig[0] - load[0]) < 1e-9
                assert abs(orig[1] - load[1]) < 1e-9
                assert abs(orig[2] - load[2]) < 0.01
        finally:
            os.unlink(path)

    def test_save_load_empty_grid(self):
        """An empty grid should survive a save/load roundtrip."""
        grid = BathymetryGrid()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            path = f.name

        try:
            grid.save(path)
            loaded = BathymetryGrid()
            loaded.load(path)
            assert loaded.total_voxels() == 0
        finally:
            os.unlink(path)

    def test_save_produces_valid_json(self):
        """The saved file should be valid JSON."""
        grid = BathymetryGrid()
        grid.fuse(56.80134, -135.30278, 73.2, _T0)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            path = f.name

        try:
            grid.save(path)
            with open(path, "r") as f2:
                data = json.load(f2)
            assert "cells" in data
            assert isinstance(data["cells"], list)
            assert len(data["cells"]) == 1
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 10. TwinCore packet handling
# ---------------------------------------------------------------------------

class TestTwinCore:
    """TwinCore should correctly route packets to state and bathymetry."""

    def test_handle_depth_packet_fuses_bathymetry(self):
        """A depth packet should be fused into the bathymetry grid."""
        core = TwinCore()
        # Set position first
        core.state.apply_packet(_make_packet("position.lat", 56.80134, _T0))
        core.state.apply_packet(_make_packet("position.lon", -135.30278, _T0))

        core.handle_packet(_make_packet("depth_m", 73.2, _T0))
        assert core.bathymetry.total_voxels() == 1

    def test_handle_depth_without_position_no_fuse(self):
        """A depth packet without position should not fuse."""
        core = TwinCore()
        core.handle_packet(_make_packet("depth_m", 73.2, _T0))
        assert core.bathymetry.total_voxels() == 0

    def test_handle_non_depth_packet(self):
        """A non-depth packet should update state but not bathymetry."""
        core = TwinCore()
        core.state.apply_packet(_make_packet("position.lat", 56.80134, _T0))
        core.state.apply_packet(_make_packet("position.lon", -135.30278, _T0))

        core.handle_packet(_make_packet("wind_kts", 8.0, _T0))
        assert core.bathymetry.total_voxels() == 0
        assert core.state.channels["wind_kts"]["value"] == 8.0
