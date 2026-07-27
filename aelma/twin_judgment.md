# AELMA Twin Core -- Parallel Build Judgment

**Date:** 2026-07-26
**Judge:** Claude Opus 4.5 (Sonnet 4.5 agent)
**Verdict:** Kimi wins overall (3 of 4 files), with Claude's bathymetry.py as a strong contender.

---

## Test Results (verified)

| Build  | Tests | Result |
|--------|-------|--------|
| Claude | 38    | 38 passed |
| Kimi   | 28    | 28 passed |

Claude has more tests (10 extra: more bearing cardinal checks, confidence edge cases,
3-sample running average, empty grid persistence, JSON validity). Kimi has fewer but
higher-quality tests (dead-reckoning between fixes, split-fix corruption check, source
merge, parametrized cardinals, confidence ladder with direct cell manipulation).

---

## File-by-File Winners

### 1. state.py -- WINNER: KIMI

**Kimi:** `build_kimi/twin/state.py` (163 lines)
**Claude:** `build_claude/twin/state.py` (257 lines)

**Justification:**

1. **Dead reckoning (Kimi lines 111-133 vs Claude: absent).** The brief explicitly
   requires "smoothed pose via dead reckoning between fixes." Kimi implements it:
   extrapolates (lat, lon) forward along heading/speed using the equirectangular
   projection. Claude simply returns the raw fix position. This is a missing feature
   in Claude.

2. **Position fix pairing (Kimi lines 94-109 vs Claude lines 152-200).** The brief
   says "A fix is complete when both components carry the same timestamp_ns."
   Kimi enforces exact timestamp match (`_lat_ts == _lon_ts == ts`), matching the
   spec precisely. Claude uses a 2-second tolerance window
   (`abs(lat_ts - lon_ts) <= 2_000_000_000`), which is more permissive but deviates
   from spec and could pair components from different fixes under burst conditions.

3. **Fix timestamp (Kimi line 109 vs Claude line 172).** Kimi uses the shared
   timestamp directly. Claude uses `max(lat_ts, lon_ts)`, introducing a minor
   temporal inconsistency when the two components arrive at slightly different times.

4. **Stale fix guard (Kimi line 100 vs Claude line 183).** Kimi explicitly rejects
   `ts <= self._last_fix[2]` (stale/duplicate). Claude has `new_ts > self._prev_pos_ts_ns`
   which is functionally equivalent but uses the derived max-timestamp rather than the
   true packet timestamp.

5. **Knots conversion precision.** Claude uses `mps / 0.514444` (6 significant figures).
   Kimi uses `1852.0 / 3600.0` (exact definition of 1 knot in m/s). The difference is
   ~0.0000004 m/s -- negligible, but Kimi is definitionally correct.

**Claude's edge:** More thorough docstrings (NumPy-style with Parameters/Returns sections).
Kimi's docstrings are concise but adequate.

---

### 2. bathymetry.py -- WINNER: KIMI (narrow)

**Kimi:** `build_kimi/twin/bathymetry.py` (158 lines)
**Claude:** `build_claude/twin/bathymetry.py` (305 lines)

**Justification:**

1. **Recency decay formula (Kimi line 103 vs Claude line 205).** This is the most
   consequential difference. The schema says "confidence drops 10% per week."
   - Kimi: exponential -- `base * 0.9^weeks` (compound decay, asymptotic to 0)
   - Claude: linear -- `base * max(0, 1 - 0.1*weeks)` (reaches exactly 0 at 10 weeks)

   "Drops 10% per week" most naturally means "loses 10% of its current value each week,"
   which is exponential. Claude's linear interpretation diverges significantly after
   2 weeks (Claude=0.40, Kimi=0.405) and dramatically after 5 weeks (Claude=0.25,
   Kimi=0.295). Claude hits zero at week 10; Kimi never does. Kimi's exponential decay
   is the more correct reading and is more physically sensible (old data fades but
   never has literally zero information value).

2. **Save format (Kimi lines 134-158 vs Claude lines 253-305).** Kimi saves clean
   schema-shaped voxels: `{lat, lon, depth_m, sample_count, last_sample_ns, source}`.
   Claude adds non-schema fields (`lat_cell`, `lon_cell`, `center_lat`, `center_lon`)
   to the JSON. While the extra keys are useful for exact reconstruction, they violate
   `additionalProperties` if the save file is ever validated against
   `bathymetry_voxel.schema.json`.

3. **Code density.** Kimi does the same work in 158 lines vs Claude's 305. Claude
   has more helper functions (`quantise_cell`, `cell_center_from_key`, `cell_center`)
   with extensive docstrings, which is good for readability but pads the file.
   Both stay under the 350-line limit.

4. **Cell center computation (tie).** Both correctly recompute the cell center from
   the quantized key. Claude stores it in the cell dict at fusion time for stability;
   Kimi recomputes it on every query. Kimi's approach is deterministic and stateless,
   which is cleaner. Claude's stored-center approach could theoretically drift if the
   ref_lat is inconsistent, but in practice it doesn't because the key determines the
   center.

**Claude's edge:** The pole-safety guard (`abs(cos_lat) < 1e-12`) is a nice defensive
touch that Kimi lacks. Also, Claude's incremental running average formula
(`cell["depth_m"] + (new - cell["depth_m"]) / (count+1)`) is numerically more stable
for large sample counts than Kimi's
(`(cell["depth_m"] * n + new) / (n+1)`), though both are correct for typical depths.

---

### 3. core.py -- WINNER: KIMI

**Kimi:** `build_kimi/twin/core.py` (193 lines)
**Claude:** `build_claude/twin/core.py` (252 lines)

**Justification:**

1. **Broadcast concurrency (Kimi lines 156-162 vs Claude lines 214-221).** Kimi uses
   `asyncio.gather()` to send snapshots to all viewers concurrently. Claude uses a
   sequential `for ws in list(self._viewers): await ws.send(raw)` loop. With multiple
   viewers, Claude's approach suffers head-of-line blocking: one slow viewer delays
   all others. Kimi's concurrent approach is the correct pattern for a broadcast server.

2. **Batch packet handling (Kimi lines 123-127 vs Claude line 167).** Kimi checks
   `isinstance(packet, list)` and iterates, handling bridge-side batching. Claude
   assumes every WebSocket frame is a single JSON object. The telemetry_packet schema
   notes "The bridge may batch multiple sensor readings into one packet," so Kimi is
   more spec-aware.

3. **Exponential backoff on bridge reconnect (Kimi lines 113-133 vs Claude lines 159-173).**
   Kimi implements exponential backoff starting at 1s, doubling to 30s max. Claude
   uses a fixed 2-second delay. Kimi's approach is better for network resilience.

4. **Snapshot assembly (Kimi lines 92-107 vs Claude lines 223-232).** Kimi's
   `build_snapshot()` method is cleanly factored and includes the bathymetry viewport
   centered on the dead-reckoned position. Claude's `_make_snapshot()` uses the raw
   fix position and hardcodes 500m viewport radius (line 227).

5. **Source mapping (Kimi lines 32-38 vs Claude line 145).** Kimi maps packet sources
   (nmea0183, simulator, signal_k, etc.) to bathymetry voxel sources (sounder, manual).
   Claude hardcodes `source="sounder"` for all depth packets, losing provenance.

6. **Initial snapshot on viewer connect (Kimi line 143 vs Claude: absent).** Kimi
   pushes an immediate snapshot when a viewer connects. Claude does not -- the viewer
   waits up to 1 second for the first broadcast. This is a UX advantage.

7. **Persist loop config (Kimi line 51 vs Claude line 55).** Kimi's `persist_interval`
   is configurable via the constructor. Claude hardcodes it to a module constant
   (`_DEFAULT_PERSIST_INTERVAL = 60.0`) and ignores any CLI override.

**Claude's edge:**
- Task lifecycle management is more explicit (lines 102-117: creates named tasks,
  cancels on shutdown, gathers return_exceptions). Kimi uses a simpler
  `asyncio.gather` without explicit cleanup.
- Final bathymetry save on shutdown (lines 249-252) -- Kimi does not save on exit.
- Viewer server binds to `0.0.0.0` (line 198) vs Kimi's `localhost` (line 187).
  Claude is correct for LAN deployment (viewers connect from other devices).
- Lazy `import websockets` inside methods means the module imports successfully
  even without websockets installed (useful for testing). Kimi imports at module level.

---

### 4. __main__.py -- WINNER: KIMI

**Kimi:** `build_kimi/twin/__main__.py` (57 lines)
**Claude:** `build_claude/twin/__main__.py` (111 lines)

**Justification:**

1. **CLI completeness.** Kimi exposes all spec-required arguments plus `--persist-interval`,
   `--viewport-radius-m`, and `--verbose`. Claude is missing `--persist-interval` and
   `--viewport-radius-m` entirely (the corresponding core parameters are hardcoded).

2. **Passing config to TwinCore.** Kimi passes all CLI args through to the constructor
   (lines 41-49). Claude's TwinCore instantiation (lines 95-101) omits
   `persist_interval` and `viewport_radius_m`.

3. **Conciseness.** Kimi does the same job in 57 lines. Claude's 111 lines include
   verbose argparse help strings and a separate `parse_args` function, which is
   good practice but more than this CLI needs.

**Claude's edge:** Separable `parse_args(argv)` function is testable. `--log-level`
with choices is more flexible than Kimi's boolean `--verbose`. Returns an exit code.

---

## Summary Scorecard

| Criterion               | Claude | Kimi  | Winner |
|-------------------------|--------|-------|--------|
| Math correctness        | Good   | Better| Kimi   |
| Schema adherence        | Good   | Better| Kimi   |
| Async correctness       | OK     | Better| Kimi   |
| Dead reckoning          | Missing| Full  | Kimi   |
| Edge case handling      | Good   | Better| Kimi   |
| Code clarity/docstrings | Better | Good  | Claude |
| Test coverage (count)   | 38     | 28    | Claude |
| Line count (all files)  | 925    | 571   | Kimi   |

---

## Bugs Found (tests missed)

### Claude

1. **No dead reckoning.** The brief explicitly requires it. `state.snapshot()`
   returns the raw fix position. Between fixes, the vessel appears stationary to
   viewers. (state.py -- design omission, not a bug per se)

2. **Linear decay reaches zero.** At 10 weeks, confidence becomes exactly 0.0.
   This means old chart data vanishes from the grid entirely. The exponential
   interpretation (Kimi) is both more natural and more useful. (bathymetry.py line 205)

3. **Broadcast head-of-line blocking.** Sequential `await ws.send()` in the
   broadcast loop means one slow viewer stalls all others. (core.py lines 215-219)

4. **No batch packet handling.** If the bridge sends a JSON array of packets,
   Claude's `json.loads` succeeds but `handle_packet` receives a list, causing a
   silent `KeyError` on `packet["channel"]`. (core.py line 167)

5. **Viewer server binds to 0.0.0.0.** This is correct for LAN deployment but
   could be a security concern in development. Kimi binds to localhost. Not a bug,
   but worth noting.

6. **persist_interval not configurable.** The `--persist-interval` CLI flag from
   the spec is missing, and the core hardcodes 60s.

### Kimi

1. **Viewer server binds to localhost.** The brief specifies LAN deployment -- a
   tablet on the vessel network needs to connect. `localhost` (core.py line 187)
   blocks external connections. Claude's `0.0.0.0` is correct for the use case.

2. **Broadcast zip alignment risk.** `list(self._viewers)` is called twice (lines
   157, 160). If a viewer disconnects between those calls (within the same event
   loop tick -- extremely unlikely but theoretically possible), the zip could
   misalign results. Should capture the list once.

3. **No final bathymetry save on shutdown.** If the process is killed between
   persist intervals, up to 60 seconds of soundings are lost. Claude saves on exit.

4. **`del viewport` in state.snapshot().** Kimi's state.py line 149 accepts the
   viewport parameter then immediately discards it with `del viewport`. The
   bathymetry block is assembled by TwinCore, not VesselState. This is a clean
   separation of concerns, but the method signature is misleading -- callers
   might expect viewport to do something in state.snapshot().

5. **websockets import at module level.** If websockets is not installed,
   `import core` fails entirely, making it impossible to test state/bathymetry
   without the dependency. Claude's lazy import avoids this.

---

## Harvest List (good ideas to steal from the loser)

### From Claude (to harvest into Kimi)

1. **Pole-safety guard in cell quantization** (bathymetry.py lines 48-50).
   `if abs(cos_lat) < 1e-12: cos_lat = 1e-12`. Prevents division by zero at
   extreme latitudes. Cheap insurance.

2. **Task lifecycle management** (core.py lines 102-117). Named tasks with
   explicit cancel + gather(return_exceptions=True) on shutdown is more robust
   than Kimi's bare gather.

3. **Final save on shutdown** (core.py lines 249-252). Ensures no data loss
   on clean exit.

4. **Bind viewer server to 0.0.0.0** (core.py line 198). Correct for LAN
   deployment on a vessel.

5. **Test coverage patterns.** Claude's tests for 3-sample running average,
   confidence at exactly 10 weeks (zero), and empty grid persistence are
   valuable additions.

6. **Separable parse_args function** (__main__.py). Enables unit testing of
   CLI argument parsing.

### From Kimi (already in winner, but noting standout ideas)

1. **Dead reckoning** (state.py lines 111-133). The clear differentiator.
2. **Exponential decay** (bathymetry.py line 103). More correct interpretation.
3. **Concurrent broadcast** (core.py lines 156-162). Correct async pattern.
4. **Batch packet handling** (core.py lines 123-127). Spec-aware.
5. **Source provenance mapping** (core.py lines 32-38). Preserves data lineage.

---

## Final Ranking

**Overall winner: KIMI** -- wins 3 of 4 files (state, bathymetry, core) plus __main__.
Claude wins on documentation thoroughness and test count, but Kimi has the
mathematically superior decay formula, the missing dead-reckoning feature, better
async patterns, and tighter code.
