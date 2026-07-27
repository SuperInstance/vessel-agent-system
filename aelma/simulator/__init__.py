"""AELMA Simulator package.

Emits realistic NMEA 0183 sentences simulating F/V EILEEN trolling in
Southeast Alaska, so the bridge and twin can be developed without real
hardware. Pure Python stdlib only.

Run with:
    python -m simulator.simulate --duration-min 0.1 --speedup 30
"""

# Intentionally do NOT eagerly import from .simulate here: doing so causes
# ``RuntimeWarning: 'simulator.simulate' found in sys.modules``
# when the user runs the module via ``python -m simulator.simulate``.
# Submodules and symbols are accessible via the normal import system, e.g.:
#     from simulator.simulate import simulate, main, depth_at
