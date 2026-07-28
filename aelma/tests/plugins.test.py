"""Tests for the AELMA plugin system: twin.plugins + example plugins.

Coverage:

  1. Plugin base class — defaults, name fallback, no-op hooks.
  2. PluginContext — emit_action records and metadata.
  3. PluginManager — register/init/shutdown lifecycle ordering.
  4. Dispatch — on_packet / on_action fan-out to all plugins.
  5. Error isolation — a raising hook never blocks the other plugins.
  6. Discovery — import from a directory, skip broken files, ignore
     non-plugin classes and imported Plugin subclasses.
  7. Example plugins — depth_anomaly rate detection and min-depth filter,
     speed_monitor rising-edge alert, reset, and on_action acknowledgment.

Run from the repo root:  python -m pytest tests/plugins.test.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.plugins import Plugin, PluginContext, PluginManager  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PLUGINS_DIR = REPO_ROOT / "plugins"


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #
class RecordingPlugin(Plugin):
    """Plugin that records every hook invocation for assertions."""

    name = "recorder"

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, object]] = []

    def load(self, context: PluginContext) -> None:
        super().load(context)
        self.calls.append(("load", context))

    def init(self, config: dict) -> None:
        self.calls.append(("init", config))

    def on_packet(self, packet: dict) -> None:
        self.calls.append(("on_packet", packet))

    def on_action(self, record: dict) -> None:
        self.calls.append(("on_action", record))

    def shutdown(self) -> None:
        self.calls.append(("shutdown", None))


class BoomPlugin(Plugin):
    """Plugin whose hooks always raise."""

    name = "boom"

    def on_packet(self, packet: dict) -> None:
        raise RuntimeError("packet boom")

    def on_action(self, record: dict) -> None:
        raise RuntimeError("action boom")

    def shutdown(self) -> None:
        raise RuntimeError("shutdown boom")


def packet(channel: str, value: float, ts_ns: int = 1_000_000_000) -> dict:
    return {"channel": channel, "value": value, "timestamp_ns": ts_ns, "source": "simulator"}


# --------------------------------------------------------------------- #
# 1. Plugin base class
# --------------------------------------------------------------------- #
def test_base_plugin_defaults() -> None:
    p = Plugin()
    assert p.name == "Plugin"  # falls back to class name
    assert p.version == "0.1.0"
    assert p.context is None
    # All hooks are safe no-ops on the base class.
    p.load(PluginContext("x"))
    p.init({})
    p.on_packet({})
    p.on_action({})
    p.shutdown()


def test_explicit_name_kept() -> None:
    p = RecordingPlugin()
    assert p.name == "recorder"


# --------------------------------------------------------------------- #
# 2. PluginContext
# --------------------------------------------------------------------- #
def test_context_emit_action_records() -> None:
    ctx = PluginContext("demo")
    rec = ctx.emit_action("raise_alert", {"kind": "test"}, reason="why", priority=0.9)
    assert rec["action"] == "raise_alert"
    assert rec["payload"] == {"kind": "test"}
    assert rec["source"] == "plugin:demo"
    assert rec["reason"] == "why"
    assert rec["priority"] == 0.9
    assert ctx.emitted == [rec]


def test_context_emit_action_defaults() -> None:
    ctx = PluginContext("demo")
    rec = ctx.emit_action("ping")
    assert rec["payload"] == {}
    assert rec["priority"] == 0.5


# --------------------------------------------------------------------- #
# 3-4. Manager lifecycle & dispatch
# --------------------------------------------------------------------- #
def test_lifecycle_order() -> None:
    mgr = PluginManager()
    p = mgr.register(RecordingPlugin())
    mgr.init_plugin(p, {"k": 1})
    mgr.shutdown_all()
    kinds = [c[0] for c in p.calls]
    assert kinds == ["load", "init", "shutdown"]
    assert p.calls[1] == ("init", {"k": 1})
    assert isinstance(p.context, PluginContext)
    assert p.context.plugin_name == "recorder"


def test_dispatch_fans_out() -> None:
    mgr = PluginManager()
    a, b = mgr.register(RecordingPlugin()), mgr.register(RecordingPlugin())
    # Give the second plugin a distinct name for clarity.
    b.name = "recorder2"
    pkt = packet("depth_m", 10.0)
    act = {"action": "raise_alert", "payload": {}}
    mgr.dispatch_packet(pkt)
    mgr.dispatch_action(act)
    assert ("on_packet", pkt) in a.calls
    assert ("on_packet", pkt) in b.calls
    assert ("on_action", act) in a.calls
    assert ("on_action", act) in b.calls


# --------------------------------------------------------------------- #
# 5. Error isolation
# --------------------------------------------------------------------- #
def test_errors_are_isolated_and_counted() -> None:
    mgr = PluginManager()
    mgr.register(BoomPlugin())
    good = mgr.register(RecordingPlugin())
    mgr.dispatch_packet(packet("depth_m", 5.0))
    mgr.dispatch_action({"action": "x"})
    mgr.shutdown_all()
    assert mgr.errors == 3  # packet + action + shutdown, all from BoomPlugin
    # The healthy plugin still received everything.
    kinds = [c[0] for c in good.calls]
    assert kinds == ["load", "on_packet", "on_action", "shutdown"]


# --------------------------------------------------------------------- #
# 6. Discovery
# --------------------------------------------------------------------- #
def test_discover_from_tmp_dir(tmp_path: Path) -> None:
    (tmp_path / "demo_plugin.py").write_text(
        "from twin.plugins import Plugin\n"
        "class DemoPlugin(Plugin):\n"
        "    name = 'demo'\n"
        "NOT_A_PLUGIN = 42\n"
    )
    (tmp_path / "helper.py").write_text("# not a *_plugin.py file: ignored\n")
    (tmp_path / "broken_plugin.py").write_text("raise SyntaxError('nope')\n")

    mgr = PluginManager()
    classes = mgr.discover(tmp_path)
    assert [c.__name__ for c in classes] == ["DemoPlugin"]
    assert mgr.errors == 1  # broken_plugin.py failed to import


def test_discover_missing_directory(tmp_path: Path) -> None:
    mgr = PluginManager()
    assert mgr.discover(tmp_path / "nope") == []


def test_load_directory_with_configs(tmp_path: Path) -> None:
    (tmp_path / "cfg_plugin.py").write_text(
        "from twin.plugins import Plugin\n"
        "class CfgPlugin(Plugin):\n"
        "    name = 'cfg'\n"
        "    def init(self, config):\n"
        "        self.got = config\n"
    )
    mgr = PluginManager()
    loaded = mgr.load_directory(tmp_path, configs={"cfg": {"answer": 42}})
    assert len(loaded) == 1
    assert loaded[0].got == {"answer": 42}


# --------------------------------------------------------------------- #
# 7. Example plugins (via discovery of the real plugins/ directory)
# --------------------------------------------------------------------- #
@pytest.fixture()
def example_manager() -> PluginManager:
    mgr = PluginManager()
    mgr.load_directory(EXAMPLE_PLUGINS_DIR)
    return mgr


def test_discovery_finds_example_plugins(example_manager: PluginManager) -> None:
    names = {p.name for p in example_manager.plugins}
    assert names == {"depth_anomaly", "speed_monitor"}
    assert example_manager.errors == 0


def _plugin(mgr: PluginManager, name: str) -> Plugin:
    return next(p for p in mgr.plugins if p.name == name)


def test_depth_anomaly_alerts_on_fast_change() -> None:
    mgr = PluginManager()
    mgr.load_directory(EXAMPLE_PLUGINS_DIR)
    p = _plugin(mgr, "depth_anomaly")
    mgr.dispatch_packet(packet("depth_m", 20.0, ts_ns=1_000_000_000))
    mgr.dispatch_packet(packet("depth_m", 15.0, ts_ns=2_000_000_000))  # 5 m/s
    alerts = p.context.emitted
    assert len(alerts) == 1
    assert alerts[0]["action"] == "raise_alert"
    assert alerts[0]["payload"]["kind"] == "depth_anomaly"
    assert alerts[0]["payload"]["rate_m_per_s"] == pytest.approx(5.0)


def test_depth_anomaly_ignores_normal_change() -> None:
    mgr = PluginManager()
    mgr.load_directory(EXAMPLE_PLUGINS_DIR)
    p = _plugin(mgr, "depth_anomaly")
    mgr.dispatch_packet(packet("depth_m", 20.0, ts_ns=1_000_000_000))
    mgr.dispatch_packet(packet("depth_m", 19.5, ts_ns=2_000_000_000))  # 0.5 m/s
    assert p.context.emitted == []


def test_depth_anomaly_ignores_shallow_noise_and_non_depth() -> None:
    mgr = PluginManager()
    mgr.load_directory(EXAMPLE_PLUGINS_DIR)
    p = _plugin(mgr, "depth_anomaly")
    mgr.dispatch_packet(packet("speed_kn", 8.0, ts_ns=1_000_000_000))
    mgr.dispatch_packet(packet("depth_m", 0.2, ts_ns=1_500_000_000))  # below min_depth
    mgr.dispatch_packet(packet("depth_m", 30.0, ts_ns=2_000_000_000))  # first valid
    assert p.context.emitted == []


def test_depth_anomaly_config_override() -> None:
    mgr = PluginManager()
    mgr.load_directory(
        EXAMPLE_PLUGINS_DIR, configs={"depth_anomaly": {"max_rate_m_per_s": 10.0}}
    )
    p = _plugin(mgr, "depth_anomaly")
    mgr.dispatch_packet(packet("depth_m", 20.0, ts_ns=1_000_000_000))
    mgr.dispatch_packet(packet("depth_m", 15.0, ts_ns=2_000_000_000))  # 5 m/s < 10
    assert p.context.emitted == []


def test_speed_monitor_alerts_on_rising_edge_only() -> None:
    mgr = PluginManager()
    mgr.load_directory(EXAMPLE_PLUGINS_DIR)
    p = _plugin(mgr, "speed_monitor")
    mgr.dispatch_packet(packet("speed_kn", 16.0))
    mgr.dispatch_packet(packet("speed_kn", 17.0))  # still over: no second alert
    assert len(p.context.emitted) == 1
    assert p.context.emitted[0]["payload"]["kind"] == "speed_limit"
    assert p.context.emitted[0]["payload"]["limit_kn"] == 15.0


def test_speed_monitor_rearms_after_reset() -> None:
    mgr = PluginManager()
    mgr.load_directory(EXAMPLE_PLUGINS_DIR)
    p = _plugin(mgr, "speed_monitor")
    mgr.dispatch_packet(packet("speed_kn", 16.0))  # alert
    mgr.dispatch_packet(packet("speed_kn", 10.0))  # below reset (13.5): re-arm
    mgr.dispatch_packet(packet("speed_kn", 16.0))  # alert again
    assert len(p.context.emitted) == 2


def test_speed_monitor_on_action_acknowledgment() -> None:
    mgr = PluginManager()
    mgr.load_directory(EXAMPLE_PLUGINS_DIR)
    p = _plugin(mgr, "speed_monitor")
    mgr.dispatch_packet(packet("speed_kn", 16.0))  # alert
    mgr.dispatch_action({"action": "reduce_speed", "payload": {}})
    mgr.dispatch_packet(packet("speed_kn", 16.0))  # ack cleared: alert again
    assert len(p.context.emitted) == 2


def test_speed_monitor_config_override() -> None:
    mgr = PluginManager()
    mgr.load_directory(
        EXAMPLE_PLUGINS_DIR,
        configs={"speed_monitor": {"max_speed_kn": 5.0, "reset_kn": 4.0}},
    )
    p = _plugin(mgr, "speed_monitor")
    mgr.dispatch_packet(packet("speed_kn", 6.0))
    assert len(p.context.emitted) == 1
    assert p.context.emitted[0]["payload"]["limit_kn"] == 5.0
