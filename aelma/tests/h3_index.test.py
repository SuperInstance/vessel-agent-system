"""Tests for the H3 geospatial index."""

import h3
import pytest

from twin.bathymetry import BathymetryGrid
from twin.h3_index import DEFAULT_RESOLUTION, H3Index

# Kodiak, AK area — waters the demo fleet operates in.
LAT, LON = 57.79, -152.40


@pytest.fixture
def index():
    return H3Index()


def test_default_resolution_is_9(index):
    assert index.resolution == 9
    assert DEFAULT_RESOLUTION == 9


def test_insert_returns_res9_cell(index):
    cell = index.insert_vessel("fv-pioneer", LAT, LON)
    assert h3.get_resolution(cell) == 9
    assert cell == h3.latlng_to_cell(LAT, LON, 9)
    assert index.cell_of("fv-pioneer") == cell
    assert index.vessel_count() == 1


def test_query_radius_finds_nearby_vessel(index):
    index.insert_vessel("fv-pioneer", LAT, LON)
    # ~500 m north: well within a 2 km query.
    index.insert_vessel("fv-explorer", LAT + 0.0045, LON)
    hits = index.query_radius(LAT, LON, 2000.0)
    assert hits == ["fv-explorer", "fv-pioneer"]


def test_query_radius_excludes_distant_vessel(index):
    index.insert_vessel("fv-pioneer", LAT, LON)
    # ~50 km away: far outside the k-ring too.
    index.insert_vessel("fv-faraway", LAT + 0.45, LON)
    assert index.query_radius(LAT, LON, 2000.0) == ["fv-pioneer"]


def test_query_radius_uses_exact_distance_not_cell(index):
    index.insert_vessel("fv-pioneer", LAT, LON)
    # Same cell or adjacent, but just past the cutoff.
    index.insert_vessel("fv-edge", LAT + 0.010, LON)  # ~1.1 km north
    hits = index.query_radius(LAT, LON, 1000.0)
    assert hits == ["fv-pioneer"]
    assert "fv-edge" in index.query_radius(LAT, LON, 1200.0)


def test_insert_moves_vessel_between_cells(index):
    old_cell = index.insert_vessel("fv-pioneer", LAT, LON)
    new_cell = index.insert_vessel("fv-pioneer", LAT + 0.09, LON)  # ~10 km
    assert new_cell != old_cell
    assert index.cell_of("fv-pioneer") == new_cell
    # Old cell no longer claims the vessel; radius at old spot is empty.
    assert index.query_radius(LAT, LON, 1000.0) == []
    assert index.query_radius(LAT + 0.09, LON, 1000.0) == ["fv-pioneer"]
    assert index.vessel_count() == 1


def test_remove_vessel(index):
    index.insert_vessel("fv-pioneer", LAT, LON)
    assert index.remove_vessel("fv-pioneer") is True
    assert index.remove_vessel("fv-pioneer") is False
    assert index.query_radius(LAT, LON, 5000.0) == []
    assert index.vessel_count() == 0


def test_get_cell_stats_vessels_only(index):
    cell = index.insert_vessel("fv-pioneer", LAT, LON)
    index.insert_vessel("fv-explorer", LAT + 0.0005, LON)  # same cell
    stats = index.get_cell_stats(cell)
    assert stats["cell"] == cell
    assert stats["resolution"] == 9
    assert stats["vessel_count"] == 2
    assert stats["vessels"] == ["fv-explorer", "fv-pioneer"]
    assert stats["voxel_count"] == 0
    assert stats["depth_mean_m"] is None


def test_get_cell_stats_unknown_cell(index):
    cell = h3.latlng_to_cell(LAT, LON, 9)
    stats = index.get_cell_stats(cell)
    assert stats["vessel_count"] == 0
    assert stats["vessels"] == []


def test_bathymetry_depth_stats():
    grid = BathymetryGrid()
    # Two soundings ~22 m apart (distinct 10 m voxels) around the target
    # cell's center, plus one far outside the cell.
    cell = h3.latlng_to_cell(LAT, LON, 9)
    clat, clon = h3.cell_to_latlng(cell)
    grid.fuse(clat + 0.0001, clon, 42.0, 1_000, source="sounder")
    grid.fuse(clat - 0.0001, clon, 58.0, 2_000, source="sounder")
    grid.fuse(LAT + 0.09, LON, 999.0, 3_000, source="sounder")
    idx = H3Index(bathymetry=grid)
    stats = idx.get_cell_stats(cell)
    assert stats["voxel_count"] == 2
    assert stats["depth_mean_m"] == 50.0
    assert stats["depth_min_m"] == 42.0
    assert stats["depth_max_m"] == 58.0
    # The far cell only sees its own deep sounding.
    far_cell = h3.latlng_to_cell(LAT + 0.09, LON, 9)
    far_stats = idx.get_cell_stats(far_cell)
    assert far_stats["voxel_count"] == 1
    assert far_stats["depth_mean_m"] == 999.0


def test_populated_cells(index):
    c1 = index.insert_vessel("fv-pioneer", LAT, LON)
    c2 = index.insert_vessel("fv-faraway", LAT + 0.45, LON)
    assert index.populated_cells() == sorted([c1, c2])
