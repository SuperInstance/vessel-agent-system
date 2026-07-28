"""Tests for the AELMA route optimizer (twin.route_optimizer).

Coverage:

  1. Waypoints — add, validation, clear.
  2. Haversine distance — known legs, symmetry, zero distance.
  3. calculate_distance — multi-leg accumulation, trivial inputs.
  4. calculate_fuel_cost — consumption model, price handling, validation.
  5. optimize_route — nearest-neighbor ordering, open vs closed routes.
  6. GPX export — structure, escaping, file output, round-trip parse.

Run from the repo root: python -m pytest tests/route_optimizer.test.py -v
"""

from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.route_optimizer import (  # noqa: E402
    BASE_L_PER_NM,
    EARTH_RADIUS_M,
    KN_TO_MPS,
    M_PER_NM,
    REFERENCE_SPEED_KN,
    RouteOptimizer,
    haversine_m,
)


# =============================================================================
# 1. Waypoints
# =============================================================================

class TestWaypoints:
    def test_add_waypoint_returns_dict(self):
        opt = RouteOptimizer()
        wp = opt.add_waypoint(58.0, -5.0, "Harbor")
        assert wp == {"lat": 58.0, "lon": -5.0, "name": "Harbor"}
        assert opt.waypoints == [wp]

    def test_add_waypoint_default_name(self):
        opt = RouteOptimizer()
        wp = opt.add_waypoint(58.0, -5.0)
        assert wp["name"] == ""

    def test_add_waypoint_validates_coordinates(self):
        opt = RouteOptimizer()
        with pytest.raises(ValueError):
            opt.add_waypoint(91.0, 0.0)
        with pytest.raises(ValueError):
            opt.add_waypoint(0.0, 181.0)

    def test_clear_waypoints(self):
        opt = RouteOptimizer()
        opt.add_waypoint(58.0, -5.0, "A")
        opt.add_waypoint(58.1, -5.1, "B")
        opt.clear_waypoints()
        assert opt.waypoints == []


# =============================================================================
# 2. Haversine distance
# =============================================================================

class TestHaversine:
    def test_zero_distance(self):
        assert haversine_m(58.0, -5.0, 58.0, -5.0) == 0.0

    def test_symmetry(self):
        d1 = haversine_m(58.0, -5.0, 59.0, -4.0)
        d2 = haversine_m(59.0, -4.0, 58.0, -5.0)
        assert d1 == pytest.approx(d2)

    def test_one_degree_latitude(self):
        # One degree of latitude is ~111 km on the spherical model.
        d = haversine_m(0.0, 0.0, 1.0, 0.0)
        expected = math.radians(1.0) * EARTH_RADIUS_M
        assert d == pytest.approx(expected, rel=1e-6)

    def test_equator_degree_longitude(self):
        # One degree of longitude at the equator equals one degree of latitude.
        d_lon = haversine_m(0.0, 0.0, 0.0, 1.0)
        d_lat = haversine_m(0.0, 0.0, 1.0, 0.0)
        assert d_lon == pytest.approx(d_lat, rel=1e-9)

    def test_antipodal(self):
        # Antipodal points are half the circumference apart.
        d = haversine_m(0.0, 0.0, 0.0, 180.0)
        assert d == pytest.approx(math.pi * EARTH_RADIUS_M, rel=1e-9)


# =============================================================================
# 3. calculate_distance
# =============================================================================

class TestCalculateDistance:
    def test_empty_and_single_point(self):
        opt = RouteOptimizer()
        assert opt.calculate_distance([]) == 0.0
        assert opt.calculate_distance([(58.0, -5.0)]) == 0.0

    def test_two_points_matches_haversine(self):
        opt = RouteOptimizer()
        pts = [(58.0, -5.0), (59.0, -4.0)]
        assert opt.calculate_distance(pts) == pytest.approx(
            haversine_m(58.0, -5.0, 59.0, -4.0)
        )

    def test_multi_leg_accumulates(self):
        opt = RouteOptimizer()
        pts = [(58.0, -5.0), (58.5, -5.0), (58.5, -4.5)]
        expected = (
            haversine_m(58.0, -5.0, 58.5, -5.0)
            + haversine_m(58.5, -5.0, 58.5, -4.5)
        )
        assert opt.calculate_distance(pts) == pytest.approx(expected)

    def test_accepts_waypoint_dicts(self):
        opt = RouteOptimizer()
        a = opt.add_waypoint(58.0, -5.0, "A")
        b = opt.add_waypoint(59.0, -4.0, "B")
        assert opt.calculate_distance([a, b]) == pytest.approx(
            opt.calculate_distance([(58.0, -5.0), (59.0, -4.0)])
        )


# =============================================================================
# 4. calculate_fuel_cost
# =============================================================================

class TestFuelCost:
    def test_reference_speed_baseline(self):
        opt = RouteOptimizer(fuel_price_per_l=1.0)
        distance_m = 10.0 * M_PER_NM  # 10 nm
        result = opt.calculate_fuel_cost(distance_m, REFERENCE_SPEED_KN)
        assert result["distance_nm"] == pytest.approx(10.0)
        assert result["fuel_liters"] == pytest.approx(10.0 * BASE_L_PER_NM)
        assert result["fuel_cost"] == pytest.approx(10.0 * BASE_L_PER_NM * 1.0)

    def test_consumption_scales_with_speed_squared(self):
        opt = RouteOptimizer()
        distance_m = 10.0 * M_PER_NM
        slow = opt.calculate_fuel_cost(distance_m, REFERENCE_SPEED_KN)
        fast = opt.calculate_fuel_cost(distance_m, REFERENCE_SPEED_KN * 2.0)
        assert fast["fuel_liters"] == pytest.approx(slow["fuel_liters"] * 4.0)

    def test_duration_from_speed(self):
        opt = RouteOptimizer()
        speed = 10.0
        distance_m = 20.0 * M_PER_NM  # 20 nm at 10 kn -> 2 h
        result = opt.calculate_fuel_cost(distance_m, speed)
        expected_h = distance_m / (speed * KN_TO_MPS) / 3600.0
        assert result["duration_h"] == pytest.approx(expected_h)
        assert result["duration_h"] == pytest.approx(2.0)

    def test_price_override(self):
        opt = RouteOptimizer(fuel_price_per_l=1.0)
        result = opt.calculate_fuel_cost(M_PER_NM, REFERENCE_SPEED_KN, fuel_price_per_l=3.0)
        assert result["fuel_cost"] == pytest.approx(BASE_L_PER_NM * 3.0)

    def test_rejects_invalid_inputs(self):
        opt = RouteOptimizer()
        with pytest.raises(ValueError):
            opt.calculate_fuel_cost(-1.0, 8.0)
        with pytest.raises(ValueError):
            opt.calculate_fuel_cost(1000.0, 0.0)


# =============================================================================
# 5. optimize_route (nearest-neighbor TSP)
# =============================================================================

class TestOptimizeRoute:
    def test_orders_nearest_first(self):
        opt = RouteOptimizer()
        start = (58.0, -5.0, "Start")
        waypoints = [
            (58.9, -5.0, "Far"),
            (58.1, -5.0, "Near"),
            (58.5, -5.0, "Mid"),
        ]
        result = opt.optimize_route(start, waypoints)
        names = [p["name"] for p in result["route"]]
        assert names == ["Start", "Near", "Mid", "Far"]

    def test_open_route_has_no_end_leg(self):
        opt = RouteOptimizer()
        result = opt.optimize_route((58.0, -5.0), [(58.1, -5.0), (58.2, -5.0)])
        assert len(result["route"]) == 3
        assert len(result["legs"]) == 2

    def test_end_appends_final_leg(self):
        opt = RouteOptimizer()
        result = opt.optimize_route(
            (58.0, -5.0, "Start"),
            [(58.1, -5.0, "A")],
            end=(58.0, -5.0, "Home"),
        )
        names = [p["name"] for p in result["route"]]
        assert names == ["Start", "A", "Home"]
        assert len(result["legs"]) == 2
        assert result["legs"][-1]["to"] == "Home"

    def test_total_distance_matches_legs(self):
        opt = RouteOptimizer()
        result = opt.optimize_route(
            (58.0, -5.0),
            [(58.1, -5.1), (58.2, -5.2), (58.05, -5.05)],
        )
        leg_sum = sum(leg["distance_m"] for leg in result["legs"])
        assert result["total_distance_m"] == pytest.approx(leg_sum)
        assert result["total_distance_m"] == pytest.approx(
            opt.calculate_distance(result["route"])
        )

    def test_uses_stored_waypoints_by_default(self):
        opt = RouteOptimizer()
        opt.add_waypoint(58.9, -5.0, "Far")
        opt.add_waypoint(58.1, -5.0, "Near")
        result = opt.optimize_route((58.0, -5.0, "Start"))
        names = [p["name"] for p in result["route"]]
        assert names == ["Start", "Near", "Far"]

    def test_nearest_neighbor_beats_naive_order(self):
        # Waypoints listed in a bad order; optimization must not do worse.
        opt = RouteOptimizer()
        start = (58.0, -5.0)
        waypoints = [(58.5, -5.0), (58.1, -5.0), (58.9, -5.0)]
        result = opt.optimize_route(start, waypoints)
        naive = opt.calculate_distance([start, *waypoints])
        assert result["total_distance_m"] <= naive + 1e-9

    def test_no_waypoints(self):
        opt = RouteOptimizer()
        result = opt.optimize_route((58.0, -5.0, "Start"), [], end=(59.0, -4.0, "End"))
        assert len(result["route"]) == 2
        assert result["total_distance_m"] == pytest.approx(
            haversine_m(58.0, -5.0, 59.0, -4.0)
        )


# =============================================================================
# 6. GPX export
# =============================================================================

GPX_NS = "{http://www.topografix.com/GPX/1/1}"


class TestGpxExport:
    def _route(self):
        opt = RouteOptimizer()
        opt.add_waypoint(58.1, -5.1, "Ground A")
        opt.add_waypoint(58.2, -5.2, "Ground B")
        return opt, opt.optimize_route((58.0, -5.0, "Harbor"))["route"]

    def test_gpx_is_valid_xml_with_route_points(self):
        _, route = self._route()
        gpx = RouteOptimizer().export_gpx(route)
        root = ET.fromstring(gpx)
        assert root.tag == f"{GPX_NS}gpx"
        rtepts = root.findall(f".//{GPX_NS}rtept")
        assert len(rtepts) == len(route)
        first = rtepts[0]
        assert float(first.attrib["lat"]) == pytest.approx(58.0)
        assert float(first.attrib["lon"]) == pytest.approx(-5.0)
        assert first.find(f"{GPX_NS}name").text == "Harbor"

    def test_gpx_escapes_special_characters(self):
        opt = RouteOptimizer()
        gpx = opt.export_gpx([(58.0, -5.0, "A & B <Ground>")], name="Fishing <Trip> & Co")
        root = ET.fromstring(gpx)  # must still parse
        assert root.find(f"{GPX_NS}name").text == "Fishing <Trip> & Co"
        rtept = root.find(f".//{GPX_NS}rtept")
        assert rtept.find(f"{GPX_NS}name").text == "A & B <Ground>"

    def test_gpx_nameless_points_omit_name_element(self):
        opt = RouteOptimizer()
        gpx = opt.export_gpx([(58.0, -5.0)])
        root = ET.fromstring(gpx)
        rtept = root.find(f".//{GPX_NS}rtept")
        assert rtept.find(f"{GPX_NS}name") is None

    def test_gpx_writes_file(self, tmp_path):
        _, route = self._route()
        out = tmp_path / "route.gpx"
        gpx = RouteOptimizer().export_gpx(route, filepath=out)
        assert out.read_text(encoding="utf-8") == gpx
        ET.parse(out)  # written file parses as XML
