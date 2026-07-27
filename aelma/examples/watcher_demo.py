#!/usr/bin/env python3
"""Demo script showing the WatcherRegistry and WatcherHistory system.

This demonstrates the AELMA watcher pattern: deterministic threshold rules
that evaluate vessel state frames and fire actions based on conditions,
with cooldown and payload deduplication to prevent alert flooding.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.watchers import WatcherRegistry, DEFAULT_PRIORITY
from twin.watcher_history import WatcherHistory, REASON_COOLDOWN, REASON_DUPLICATE
from schema.actions import VESSEL_ACTION_SCHEMAS


def demo_basic_registry():
    """Basic watcher registry without history."""
    print("\n" + "="*60)
    print("DEMO 1: Basic Registry (No History)")
    print("="*60)

    registry = WatcherRegistry(verbose=True)

    # Add a shallow water warning rule
    registry.add({
        "id": "shallow-water",
        "name": "Shallow water warning",
        "when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {
                "severity": "warning",
                "code": "SHALLOW_WATER",
                "message": f"Depth {f['depth_m']:.1f}m - shallow water detected"
            },
            "reason": lambda f: f"depth={f['depth_m']:.2f}m",
            "priority": lambda f: 0.85,
        },
    })

    # Add a speed warning rule
    registry.add({
        "id": "high-speed",
        "name": "High speed warning",
        "when": lambda f: f.get("speed_kn", 0) > 10.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {
                "severity": "info",
                "code": "HIGH_SPEED",
                "message": f"Speed {f['speed_kn']:.1f} knots - consider reducing"
            },
            "reason": lambda f: f"speed={f['speed_kn']:.1f}kn",
            "priority": lambda f: 0.6,
        },
    })

    # Test with shallow water frame
    frame = {
        "lat": 57.0531,
        "lon": -135.33,
        "depth_m": 1.2,
        "speed_kn": 5.4,
        "heading_deg": 214.5,
    }

    actions = registry.evaluate(frame)
    print(f"\nShallow water frame ({frame['depth_m']}m): {len(actions)} actions fired")
    for action in actions:
        print(f"  - {action['action']}: {action['payload']['message']} (priority: {action['priority']})")

    # Test with normal depth frame
    frame_normal = {**frame, "depth_m": 15.0}
    actions = registry.evaluate(frame_normal)
    print(f"\nNormal depth frame ({frame_normal['depth_m']}m): {len(actions)} actions fired")


def demo_cooldown_and_history():
    """Watcher with cooldown and payload deduplication."""
    print("\n" + "="*60)
    print("DEMO 2: Cooldown and Payload Deduplication")
    print("="*60)

    clock = [1000.0]  # Mutable clock for deterministic testing
    def now():
        return clock[0]

    history = WatcherHistory(default_cooldown_s=30.0)
    registry = WatcherRegistry(history=history, now=now, verbose=True)

    # Add rule with 10-second cooldown
    registry.add({
        "id": "low-fuel",
        "name": "Low fuel warning",
        "when": lambda f: f.get("fuel_percent", 100) < 20,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {
                "severity": "warning",
                "code": "LOW_FUEL",
                "message": f"Fuel at {f['fuel_percent']:.0f}%"
            },
            "reason": lambda f: f"fuel={f['fuel_percent']:.0f}%",
            "priority": lambda f: 0.9,
        },
        "cooldown_s": 10.0,
    })

    # First fire (t=1000)
    frame1 = {"fuel_percent": 15}
    actions1 = registry.evaluate(frame1)
    print(f"\nFirst evaluation (t={clock[0]}): {len(actions1)} actions fired")

    # Immediate retry (t=1000) - should be suppressed (duplicate payload)
    actions2 = registry.evaluate(frame1)
    print(f"Immediate retry (t={clock[0]}): {len(actions2)} actions fired")
    stats = history.get_stats()["rules"]["low-fuel"]
    print(f"  - History: {stats['total_fires']} fires, {stats['total_suppressed']} suppressed")
    print(f"  - Last reason: {stats['last_suppressed_reason']}")

    # Advance time slightly, still in cooldown (t=1005)
    clock[0] = 1005.0
    frame2 = {"fuel_percent": 18}  # Different payload (changed value)
    actions3 = registry.evaluate(frame2)
    print(f"\nStill in cooldown, changed payload (t={clock[0]}): {len(actions3)} actions fired")
    stats = history.get_stats()["rules"]["low-fuel"]
    print(f"  - History: {stats['total_fires']} fires, {stats['total_suppressed']} suppressed")
    print(f"  - Last reason: {stats['last_suppressed_reason']}")

    # Advance past cooldown (t=1015)
    clock[0] = 1015.0
    actions4 = registry.evaluate(frame2)
    print(f"\nPast cooldown (t={clock[0]}): {len(actions4)} actions fired")
    stats = history.get_stats()["rules"]["low-fuel"]
    print(f"  - History: {stats['total_fires']} fires, {stats['total_suppressed']} suppressed")


def demo_async_stream():
    """Async watcher evaluation over a frame stream."""
    print("\n" + "="*60)
    print("DEMO 3: Async Frame Stream Processing")
    print("="*60)

    async def frame_stream():
        """Simulated vessel telemetry stream."""
        frames = [
            {"depth_m": 15.0, "speed_kn": 5.0, "temp_c": 18.5},  # Normal
            {"depth_m": 1.8, "speed_kn": 5.0, "temp_c": 18.5},  # Shallow!
            {"depth_m": 1.7, "speed_kn": 5.0, "temp_c": 18.5},  # Still shallow (suppressed)
            {"depth_m": 12.0, "speed_kn": 11.5, "temp_c": 18.5},  # Fast!
            {"depth_m": 13.0, "speed_kn": 6.0, "temp_c": 18.5},  # Normal
        ]
        for i, frame in enumerate(frames):
            print(f"\n[Frame {i+1}] depth={frame['depth_m']}m, speed={frame['speed_kn']}kn")
            yield frame
            await asyncio.sleep(0.1)  # Simulate real-time stream

    history = WatcherHistory()
    registry = WatcherRegistry(history=history)

    # Shallow water rule
    registry.add({
        "id": "shallow-water",
        "name": "Shallow water warning",
        "when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {
                "severity": "warning",
                "code": "SHALLOW_WATER",
                "message": f"Depth {f['depth_m']:.1f}m"
            },
            "reason": lambda f: f"depth={f['depth_m']:.2f}m",
            "priority": lambda f: 0.85,
        },
        "cooldown_s": 5.0,
    })

    # High speed rule
    registry.add({
        "id": "high-speed",
        "name": "High speed warning",
        "when": lambda f: f.get("speed_kn", 0) > 10.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {
                "severity": "info",
                "code": "HIGH_SPEED",
                "message": f"Speed {f['speed_kn']:.1f}kn"
            },
            "reason": lambda f: f"speed={f['speed_kn']:.1f}kn",
            "priority": lambda f: 0.6,
        },
        "cooldown_s": 3.0,
    })

    # Track fired actions
    fired_actions = []

    async def dispatch(action):
        fired_actions.append(action)
        print(f"  >>> FIRED: {action['action']} - {action['payload']['message']} "
              f"(priority: {action['priority']})")

    # Process the stream
    asyncio.run(registry.run(frame_stream(), dispatch))

    print(f"\n\nStream processing complete. Total actions fired: {len(fired_actions)}")
    stats = history.get_stats()
    print(f"History stats: {stats['total_fires']} fires, {stats['total_suppressed']} suppressed")


def demo_vessel_actions():
    """Show available vessel action schemas."""
    print("\n" + "="*60)
    print("DEMO 4: Available Vessel Action Schemas")
    print("="*60)

    print("\nDefined vessel actions:")
    for action_name in sorted(VESSEL_ACTION_SCHEMAS.keys()):
        schema = VESSEL_ACTION_SCHEMAS[action_name]
        print(f"\n  {action_name}:")
        print(f"    Description: {schema['description']}")
        print(f"    Required fields: {', '.join(schema['required'])}")
        if schema['properties']:
            print(f"    Optional fields: {', '.join([k for k in schema['properties'] if k not in schema['required']])}")


def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("AELMA WatcherRegistry System Demonstration")
    print("="*60)
    print("\nThis demo shows the watcher pattern: deterministic threshold")
    print("rules that evaluate vessel state and fire actions with cooldown")
    print("and payload deduplication to prevent alert flooding.")

    demo_basic_registry()
    demo_cooldown_and_history()
    demo_async_stream()
    demo_vessel_actions()

    print("\n" + "="*60)
    print("Demo complete!")
    print("="*60)
    print("\nKey features demonstrated:")
    print("  - Rule registration and validation")
    print("  - Frame evaluation and action generation")
    print("  - Cooldown enforcement (time-based suppression)")
    print("  - Payload deduplication (hash-based suppression)")
    print("  - Async stream processing")
    print("  - Vessel action schemas with validation")


if __name__ == "__main__":
    main()
