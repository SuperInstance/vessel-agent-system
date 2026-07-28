"""Demo of fishing mode manager functionality."""

import time
from build_kimi.twin.core import TwinCore
from build_kimi.twin.fishing_modes import FishingMode


def demo_basic_mode_management():
    """Demonstrate basic fishing mode management."""
    print("\n" + "="*60)
    print("FISHING MODE MANAGER DEMO")
    print("="*60 + "\n")

    # Initialize twin core
    twin = TwinCore(enable_watchers=True)
    print("[OK] TwinCore initialized with fishing mode manager")

    # Get initial mode
    mode = twin.get_fishing_mode()
    print(f"\nInitial mode: {mode['current_mode']}")
    print(f"Reason: {mode['reason']}")
    print(f"Duration: {mode['duration_s']:.2f}s")

    # Simulate a fishing operation
    print("\n" + "-"*60)
    print("SIMULATING FISHING OPERATION")
    print("-"*60)

    operations = [
        (FishingMode.TRANSIT, "Departing port for fishing grounds"),
        (FishingMode.FISHING, "Arrived at fishing grounds"),
        (FishingMode.GEAR_DEPLOYED, "Deploying gear"),
        (FishingMode.FISHING, "Gear set, fishing active"),
        (FishingMode.HAULING, "Hauling gear"),
        (FishingMode.TRANSIT, "Returning to port"),
    ]

    for i, (fishing_mode, reason) in enumerate(operations, 1):
        print(f"\nStep {i}: {fishing_mode.value}")
        print(f"  Reason: {reason}")

        # Set mode
        twin.set_fishing_mode(fishing_mode, reason)

        # Get current mode info
        mode_info = twin.get_fishing_mode()
        print(f"  Duration: {mode_info['duration_s']:.2f}s")
        print(f"  Transitions: {mode_info.get('transitions', 'N/A')}")

        # Small delay to simulate time passing
        time.sleep(0.1)

    print("\n" + "-"*60)
    print("MODE HISTORY")
    print("-"*60)

    # Show mode history
    history = twin.get_fishing_mode_history()
    for transition in history:
        from_mode = transition['from_mode'] or 'START'
        to_mode = transition['to_mode']
        print(f"  {from_mode} -> {to_mode}: {transition['reason']}")

    print("\n" + "-"*60)
    print("MODE STATISTICS")
    print("-"*60)

    # Show statistics
    stats = twin.get_fishing_mode_statistics()
    print(f"Total transitions: {stats['total_transitions']}")

    for mode_name, mode_stats in sorted(stats['modes'].items()):
        duration_s = mode_stats['total_duration_ns'] / 1e9
        entry_count = mode_stats['entry_count']

        if entry_count > 0:
            print(f"\n{mode_name}:")
            print(f"  Entries: {entry_count}")
            print(f"  Total time: {duration_s:.2f}s")
            if duration_s > 0:
                avg_duration = duration_s / entry_count
                print(f"  Avg per entry: {avg_duration:.3f}s")


def demo_mode_specific_watchers():
    """Demonstrate mode-specific watcher rules."""
    print("\n" + "="*60)
    print("MODE-SPECIFIC WATCHER DEMO")
    print("="*60 + "\n")

    # Initialize twin core with watchers enabled
    twin = TwinCore(enable_watchers=True)
    print("[OK] TwinCore initialized with mode-specific watchers")

    # Set mode to FISHING
    twin.set_fishing_mode(FishingMode.FISHING, "Fishing in shallow water")
    print(f"\n[OK] Set mode to: {twin.get_fishing_mode()['current_mode']}")

    # Inject shallow depth telemetry
    print("\nInjecting telemetry: depth_m = 3.5m (critical for fishing)")
    twin.handle_packet({
        "timestamp_ns": 0,
        "source": "simulator",
        "channel": "depth_m",
        "value": 3.5,
        "quality": "good",
    })

    # Inject speed telemetry
    print("Injecting telemetry: speed_kn = 8.5kn")
    twin.handle_packet({
        "timestamp_ns": 0,
        "source": "simulator",
        "channel": "speed_kn",
        "value": 8.5,
        "quality": "good",
    })

    # Check watcher stats
    stats = twin.get_watcher_stats()
    print(f"\nWatcher fires: {stats['history']['total_fires']}")
    print(f"Watcher suppressions: {stats['history']['total_suppressed']}")

    # List registered watchers
    print("\nRegistered watchers (sample):")
    for watcher in stats['rules'][:5]:
        print(f"  - {watcher['id']}: {watcher.get('action', 'N/A')}")

    print("\n[OK] Mode-specific watchers enable context-aware alerting")


def demo_snapshot_includes_mode():
    """Demonstrate that snapshots include fishing mode."""
    print("\n" + "="*60)
    print("SNAPSHOT INTEGRATION DEMO")
    print("="*60 + "\n")

    twin = TwinCore()
    twin.set_fishing_mode(FishingMode.FISHING, "Active fishing")

    # Build snapshot
    snapshot = twin.build_snapshot()

    print("[OK] Snapshot includes fishing_mode field:")
    mode_info = snapshot['fishing_mode']
    print(f"  Current mode: {mode_info['current_mode']}")
    print(f"  Duration: {mode_info['duration_s']:.2f}s")
    print(f"  Reason: {mode_info['reason']}")


def demo_watcher_frame_context():
    """Demonstrate watcher frame includes fishing mode context."""
    print("\n" + "="*60)
    print("WATCHER FRAME CONTEXT DEMO")
    print("="*60 + "\n")

    twin = TwinCore()
    twin.set_fishing_mode(FishingMode.FISHING, "Fishing operation")

    # Build watcher frame (internal access for demo)
    frame = twin._build_frame()

    print("[OK] Watcher frame includes fishing mode context:")
    print(f"  fishing_mode: {frame['fishing_mode']}")
    print(f"  fishing_mode_duration_s: {frame['fishing_mode_duration_s']:.2f}")
    print(f"  fishing_mode_transitions: {frame['fishing_mode_transitions']}")


def main():
    """Run all demos."""
    demo_basic_mode_management()
    demo_mode_specific_watchers()
    demo_snapshot_includes_mode()
    demo_watcher_frame_context()

    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60 + "\n")
    print("Key Features:")
    print("  • Track vessel operational modes (TRANSIT, FISHING, etc.)")
    print("  • Time-in-mode tracking with statistics")
    print("  • Full mode change history")
    print("  • Mode-specific watcher rules")
    print("  • Context-aware alerting")
    print("  • Integration with VesselStateSnapshot")
    print()


if __name__ == "__main__":
    main()
