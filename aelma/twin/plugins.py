"""Plugin system: third-party extensions for the AELMA twin.

A plugin is a subclass of :class:`Plugin` living in a ``*_plugin.py`` file
inside the ``plugins/`` directory. The :class:`PluginManager` discovers,
loads, and drives plugins through a fixed lifecycle::

    load(context) -> init(config) -> on_packet(packet)* / on_action(record)*
                                   -> shutdown()

Design contracts (same spirit as the watcher layer):

* Hooks are synchronous and cheap — they run inside the packet hot path.
  Exceptions raised by a hook are isolated by the manager: the failing
  call is logged and counted, and the remaining plugins still run.
* Plugins never modify core code. They observe telemetry packets and A2A
  action records, and they emit new actions through
  :meth:`PluginContext.emit_action`.
* Discovery uses :mod:`importlib` on plain files, so dropping a new
  ``*_plugin.py`` into ``plugins/`` is the entire install procedure.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("aelma.twin.plugins")

#: File suffix scanned during discovery in the plugins directory.
PLUGIN_SUFFIX = "_plugin.py"


class PluginContext:
    """Handle passed to :meth:`Plugin.load`; the plugin's view of the host.

    ``emit_action`` records an action the plugin wants the twin to take.
    The host (e.g. :class:`~twin.core.TwinCore`) drains ``emitted`` and
    forwards entries to ``TwinCore.log_action``; in tests and standalone
    use the list itself is the observable output.
    """

    def __init__(self, plugin_name: str, twin: Any = None) -> None:
        self.plugin_name = plugin_name
        self.twin = twin
        self.logger = logging.getLogger(f"aelma.plugin.{plugin_name}")
        self.emitted: list[dict[str, Any]] = []

    def emit_action(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        *,
        reason: str = "",
        priority: float = 0.5,
    ) -> dict[str, Any]:
        """Record an A2A action for the host to log; returns the record."""
        record = {
            "action": action,
            "payload": payload or {},
            "source": f"plugin:{self.plugin_name}",
            "reason": reason,
            "priority": priority,
        }
        self.emitted.append(record)
        self.logger.info("emit %s: %s", action, reason)
        return record


class Plugin:
    """Base class for AELMA twin plugins.

    Subclasses override whichever lifecycle hooks they need; all hooks
    are no-ops by default. Class attributes give the plugin its identity:

    * ``name`` — unique plugin id (defaults to the class name).
    * ``version`` — free-form version string.
    * ``description`` — one line shown in logs and listings.
    """

    name: str = ""
    version: str = "0.1.0"
    description: str = ""

    def __init__(self) -> None:
        if not self.name:
            self.name = type(self).__name__
        self.context: PluginContext | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle hooks — override as needed; all must stay synchronous.
    # ------------------------------------------------------------------ #
    def load(self, context: PluginContext) -> None:
        """Called once when the plugin is loaded; store the context here."""
        self.context = context

    def init(self, config: dict[str, Any]) -> None:
        """Called after load with the plugin's config dict (may be empty)."""

    def on_packet(self, packet: dict[str, Any]) -> None:
        """Called for every telemetry packet ingested by the twin."""

    def on_action(self, record: dict[str, Any]) -> None:
        """Called for every A2A action record logged by the twin."""

    def shutdown(self) -> None:
        """Called once when the host stops; release any resources."""


class PluginManager:
    """Discovers, loads, and dispatches to plugins with error isolation."""

    def __init__(self, twin: Any = None) -> None:
        self.twin = twin
        self.plugins: list[Plugin] = []
        self.errors: int = 0

    # ------------------------------------------------------------------ #
    # Discovery & loading
    # ------------------------------------------------------------------ #
    def discover(self, directory: str | Path) -> list[type[Plugin]]:
        """Import every ``*_plugin.py`` in *directory* and return the
        :class:`Plugin` subclasses defined in them. Unimportable files are
        logged and skipped — one broken plugin must not block the rest."""
        directory = Path(directory)
        found: list[type[Plugin]] = []
        if not directory.is_dir():
            log.warning("plugin directory %s does not exist; skipping", directory)
            return found
        for path in sorted(directory.glob(f"*{PLUGIN_SUFFIX}")):
            module_name = f"aelma_plugin_{path.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"cannot build module spec for {path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            except Exception as exc:  # noqa: BLE001 — isolate bad plugins
                log.error("failed to import plugin %s: %s", path, exc)
                self.errors += 1
                continue
            for attr in vars(module).values():
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Plugin)
                    and attr is not Plugin
                    and attr.__module__ == module.__name__
                ):
                    found.append(attr)
                    log.info("discovered plugin %s in %s", attr.__name__, path)
        return found

    def register(self, plugin: Plugin) -> Plugin:
        """Instantiate-phase: attach a context and run ``load()``."""
        context = PluginContext(plugin.name, twin=self.twin)
        try:
            plugin.load(context)
        except Exception as exc:  # noqa: BLE001
            log.error("plugin %s load() failed: %s", plugin.name, exc)
            self.errors += 1
        self.plugins.append(plugin)
        return plugin

    def load_directory(
        self,
        directory: str | Path,
        configs: dict[str, dict[str, Any]] | None = None,
    ) -> list[Plugin]:
        """Discover, register, and init every plugin in *directory*.

        ``configs`` maps plugin name to its config dict passed to
        :meth:`Plugin.init`. Returns the plugins actually loaded.
        """
        configs = configs or {}
        loaded = []
        for cls in self.discover(directory):
            plugin = self.register(cls())
            self.init_plugin(plugin, configs.get(plugin.name, {}))
            loaded.append(plugin)
        return loaded

    def init_plugin(self, plugin: Plugin, config: dict[str, Any]) -> None:
        """Run ``init()`` for one already-registered plugin."""
        try:
            plugin.init(config)
        except Exception as exc:  # noqa: BLE001
            log.error("plugin %s init() failed: %s", plugin.name, exc)
            self.errors += 1

    # ------------------------------------------------------------------ #
    # Dispatch
    # ------------------------------------------------------------------ #
    def dispatch_packet(self, packet: dict[str, Any]) -> None:
        """Fan one telemetry packet out to every plugin's ``on_packet``."""
        for plugin in self.plugins:
            try:
                plugin.on_packet(packet)
            except Exception as exc:  # noqa: BLE001
                log.error("plugin %s on_packet() failed: %s", plugin.name, exc)
                self.errors += 1

    def dispatch_action(self, record: dict[str, Any]) -> None:
        """Fan one A2A action record out to every plugin's ``on_action``."""
        for plugin in self.plugins:
            try:
                plugin.on_action(record)
            except Exception as exc:  # noqa: BLE001
                log.error("plugin %s on_action() failed: %s", plugin.name, exc)
                self.errors += 1

    # ------------------------------------------------------------------ #
    # Shutdown
    # ------------------------------------------------------------------ #
    def shutdown_all(self) -> None:
        """Run ``shutdown()`` on every plugin, isolating failures."""
        for plugin in self.plugins:
            try:
                plugin.shutdown()
            except Exception as exc:  # noqa: BLE001
                log.error("plugin %s shutdown() failed: %s", plugin.name, exc)
                self.errors += 1
