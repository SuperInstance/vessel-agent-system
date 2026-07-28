#!/usr/bin/env python3
"""Simple TwinCore test server for dashboard testing."""

import asyncio
import json
import time
import websockets
import math

async def send_test_snapshots(websocket, path):
    """Send simulated vessel state snapshots for dashboard testing."""
    print(f"Client connected from {websocket.remote_address}")

    # Initial state
    lat = 56.80134
    lon = -135.30278
    heading = 215.0
    speed = 4.2
    depth = 73.2
    temp = 9.5
    wind = 8.0
    rpm = 1200

    # Bathymetry cells
    bathymetry_cells = []
    for i in range(20):
        for j in range(20):
            cell_lat = lat + (i - 10) * 0.001
            cell_lon = lon + (j - 10) * 0.001
            cell_depth = depth + math.sin(i * 0.5) * 10 + math.cos(j * 0.5) * 5
            bathymetry_cells.append([cell_lat, cell_lon, cell_depth, 0.85])

    try:
        while True:
            # Simulate changing conditions
            now = time.time_ns()
            lat += (math.sin(time.time() * 0.1) * 0.0001)
            lon += (math.cos(time.time() * 0.1) * 0.0001)
            heading = (heading + math.sin(time.time() * 0.2) * 0.5) % 360
            speed = max(0, speed + math.sin(time.time() * 0.3) * 0.1)
            depth = max(2.5, depth + math.sin(time.time() * 0.15) * 0.5)
            temp = max(5, temp + math.sin(time.time() * 0.05) * 0.2)
            wind = max(0, wind + math.sin(time.time() * 0.25) * 0.5)
            rpm = max(800, rpm + math.sin(time.time() * 0.1) * 50)

            # Create snapshot
            snapshot = {
                "timestamp_ns": now,
                "vessel_id": "US-AK-FVEILEEN-51",
                "pose": {
                    "lat": lat,
                    "lon": lon,
                    "heading_deg": heading,
                    "speed_kn": speed
                },
                "channels": {
                    "depth_m": {"value": depth, "timestamp_ns": now, "quality": "good"},
                    "sea_temp_c": {"value": temp, "timestamp_ns": now, "quality": "good"},
                    "wind_kts": {"value": wind, "timestamp_ns": now, "quality": "good"},
                    "engine_rpm": {"value": rpm, "timestamp_ns": now, "quality": "good"}
                },
                "bathymetry": {
                    "voxel_count": 1842,
                    "viewport_center": {"lat": lat, "lon": lon},
                    "viewport_radius_m": 500,
                    "cells": bathymetry_cells
                }
            }

            await websocket.send(json.dumps(snapshot))
            await asyncio.sleep(1.0)  # 1 Hz update rate

    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected")

    except Exception as e:
        print(f"Error: {e}")

async def main():
    """Start the test TwinCore server."""
    print("Starting test TwinCore server on ws://localhost:8090")
    print("Connect the dashboard to test telemetry display")

    async with websockets.serve(send_test_snapshots, "localhost", 8090):
        print("Server running. Press Ctrl+C to stop.")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
