# AELMA Viewer Build Competition -- Judgment

**Date:** 2026-07-26
**Judge:** Claude Opus 4.5 (Sonnet 4.5 agent)
**Brief:** `schema/shared_viewer_brief.md`
**Wire contract:** `schema/vessel_state.schema.json`

---

## Implementations

| | Implementation A (Claude) | Implementation B (Kimi) |
|---|---|---|
| **Location** | `build_claude/viewer/` | `build_kimi_viewer/` |
| **Files** | index.html, style.css, app.js, serve.py, README.md | index.html, style.css, app.js, serve.py, README.md |
| **Payload (excl. CDN)** | 32,770 bytes (~32.0 KB) | 20,426 bytes (~19.9 KB) |
| **Line count** | 1,253 | 633 |

Both are well under the 50 KB budget.

---

## Feature-by-Feature Comparison

| # | Brief Requirement | A (Claude) | B (Kimi) | Notes |
|---|---|---|---|---|
| 1 | **index.html** -- single-file entry, Three.js from CDN | YES | YES | B uses an import map (`index.html` L8-15); A uses direct URL imports in `app.js` L13-14. Both load from `https://unpkg.com/three@0.160.0/build/three.module.js`. |
| 2 | **style.css** -- separate file, dark nautical, 320px sidebar right, responsive iPad | YES | YES | A has 413 lines of polished CSS with CSS variables, card hover states, a reconnect overlay with spinner, and 3 breakpoints. B has 159 lines -- lean but covers the same ground. |
| 3 | **app.js** -- separate ES module importing Three.js | YES | YES | A: 611 lines, function-organized. B: 327 lines, top-down linear. |
| 4 | **Three.js from CDN** (`https://unpkg.com/three@0.160.0/build/three.module.js`) | YES | YES | A imports directly in app.js. B uses import map in HTML then `import * as THREE from 'three'`. |
| 5 | **WebSocket with auto-reconnect** (exponential backoff capped at 5s) | YES | YES | A: starts at 500ms, doubles, caps at 5000ms (app.js L21-22, L548-560). B: starts at 250ms, doubles, caps at 5000ms (app.js L277, L301-304). Both display reconnect countdown text. |
| 6 | **ENU projection** (x = dlon*111000*cos(lat0), z = dlat*111000, y = -depth) | YES | YES | A: app.js L230-242. B: app.js L145-157. Both center on first received position. |
| 7 | **Vessel mesh: cone hull (8m) + box cabin (3m), orange #ff7700** | YES | YES | A: ConeGeometry(2, 8, 8) + BoxGeometry(3, 2.4, 3) + mast (app.js L155-184). B: ConeGeometry(2.2, 8, 12) + BoxGeometry(2.6, 2.2, 3) (app.js L81-92). A adds a mast cylinder -- nice detail. |
| 8 | **Bathymetry point cloud: BufferGeometry, per-vertex color from depth** | YES | YES | A: pre-allocates 50000 points (app.js L204-224). B: pre-allocates 200000 points (app.js L118-131). Both use Float32Array with RGBA color attributes. |
| 9 | **Depth colors: <30m warm orange, 30-80m green, >80m blue** | YES | YES | A: app.js L248-259 returns {r,g,b}. B: app.js L133-135 uses THREE.Color constants. Both are exactly the right bands. |
| 10 | **Opacity from confidence** | PARTIAL | YES | A stores confidence in the 4th color component (app.js L325) but uses PointsMaterial which ignores per-vertex alpha unless GLSL blending is configured -- the confidence value is stored but may not visually affect rendering with standard PointsMaterial. B also stores alpha in the 4th component (app.js L141) with the same caveat, but clamps it to [0.1, 1.0]. Both have the same theoretical limitation with PointsMaterial. Edge: B for clamping. |
| 11 | **Water surface: semi-transparent blue plane at y=0, 1000x1000m** | YES | YES | A: MeshBasicMaterial, 0.45 opacity, animated shimmer (app.js L137-149, L492-494). B: MeshPhongMaterial with shininess 90, 0.55 opacity (app.js L68-76). A's shimmer animation is a nice touch. |
| 12 | **Track line: orange, last 500 positions** | YES | YES | A: app.js L187-202, uses shift() on JS array then copies to buffer. B: app.js L95-116, uses `copyWithin` on the Float32Array -- more efficient (no GC pressure). |
| 13 | **Hemisphere + directional lighting** | YES | YES | A: HemisphereLight(0.87ceeb, 0x0a1628, 0.6) + DirectionalLight(0xffffff, 0.8) at (50,100,30) -- app.js L108-113. B: HemisphereLight(0xcfe8ff, 0x1a2f45, 1.1) + DirectionalLight(0xfff2dd, 1.6) at (200,400,150) -- app.js L62-65. B's lighting is brighter/warmer. |
| 14 | **Sky-blue background + fog** | YES | YES | A: 0x87ceeb, Fog 300-900 (app.js L82-83). B: 0x87b5d9, Fog 400-2500 (app.js L37-38). B's fog range is better suited for the larger bathymetry area. |
| 15 | **OrbitControls from Three.js addons** | YES | YES | Both import from `https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js`. |
| 16 | **Auto-rotate after 5s of no input** | YES | YES | A: event listeners on pointerdown/move/wheel/touch, checks in animate loop (app.js L454-468). B: uses OrbitControls 'start' event + pointer/wheel/touch listeners, checks in animation loop (app.js L54-59, L324). Both 5000ms. |
| 17 | **Touch controls for iPad (pinch zoom, drag rotate)** | YES | YES | A: relies on OrbitControls defaults + registers touch events for auto-rotate detection. B: explicitly sets `controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN }` (app.js L51) -- more explicit and resilient to future OrbitControls changes. |
| 18 | **Sidebar DOM: header (vessel_id, status dot)** | YES | YES | Both update vessel_id and status dot on connect/disconnect. |
| 19 | **Big depth readout (color by quality)** | YES | YES | A: 48px, quality classes quality-good/warning/bad (app.js L346-352, CSS L171-181). B: 52px, q-good/fair/bad/none (app.js L185-191, CSS L87-90). A uses "quality-warning" for the "fair" quality level -- a naming inconsistency (CSS has `.quality-warning` not `.quality-fair`), but it works. |
| 20 | **Grid of channel readouts** | YES | YES | A: dynamically creates channel cards with label map and unit map (app.js L374-410). B: dynamically creates channel cards with regex-based unit extraction (app.js L208-221). A's approach is more curated; B's is more generic. |
| 21 | **Voxel count in sidebar** | YES | YES | Both display bathymetry.voxel_count with locale formatting and pulse animation. |
| 22 | **Session duration** | YES | YES | A: starts on first WS connect (app.js L521-523), updates every 1s, MM:SS format. B: starts at page load (app.js L160), updates every 1s, supports HH:MM:SS for long sessions. B's session timer actually starts before connection -- slightly different semantics but arguably better (tracks total page time). |
| 23 | **CSS pulse animation on value updates** | YES | YES | A: brightness scale pulse `value-pulse` (CSS L322-335). B: text-shadow glow pulse `pulse` (CSS L134-139). Both use the reflow trick to restart animation. |
| 24 | **serve.py** -- Python http.server, CORS headers, argparse --port | YES | YES | A: app.js L1-70, also adds --host and --dir options, uses socketserver.TCPServer. B: serve.py L1-45, uses ThreadingTCPServer + allow_reuse_address, adds Cache-Control: no-store. B is more robust for concurrent requests. |
| 25 | **serve.py has --port** | YES | YES | A: default 8080, also --host and --dir. B: default 8080. |
| 26 | **serve.py has CORS headers** | YES | YES | Both send Access-Control-Allow-Origin: *, Methods, Headers. |
| 27 | **README.md** -- quickstart | YES | YES | A: 89 lines, includes test snapshot injection instructions. B: 51 lines, clean and concise. |
| 28 | **Speed and heading in sidebar** | YES | YES | A: dedicated meta-panel rows for speed and heading (HTML L38-45). B: channels created dynamically for speed/heading (app.js L179-180). |
| 29 | **Position display** | YES | YES | Both show lat/lon to 5 decimal places. |
| 30 | **Camera initial position targets vessel** | NO | YES | A: camera at fixed (50, 60, 80), never re-targets to vessel. B: on first snapshot, snaps camera target and position to vessel location (app.js L255-259). This is a meaningful UX advantage for B. |
| 31 | **Reconnect overlay UI** | YES | NO | A: full-screen overlay with spinner and countdown text (HTML L61-66, CSS L278-318). B: updates the connection status text in the sidebar header only. A provides better visual feedback during disconnection. |
| 32 | **`frustumCulled = false` on track/points** | NO | YES | A does not set this. B sets it on both track and bathymetry (app.js L103, L129). This prevents points from disappearing when the bounding sphere hasn't been computed yet -- an important Three.js correctness fix. |
| 33 | **ThreadingTCPServer** | NO | YES | A uses `socketserver.TCPServer` (serve.py L58) which handles one request at a time. B uses `socketserver.ThreadingTCPServer` (serve.py L35) which handles concurrent requests -- important for serving modules + CSS + JS simultaneously. |
| 34 | **Cache-Control: no-store** | NO | YES | B adds this header (serve.py L22). A does not. Important for development -- prevents stale module caching. |
| 35 | **Import map for clean imports** | NO | YES | B uses an import map in index.html, allowing `import * as THREE from 'three'` instead of full URLs. More maintainable, easier to version-bump. |
| 36 | **Track line: efficient ring buffer** | NO | YES | A uses JS array shift() (app.js L276-278) -- O(n) per shift, causes GC. B uses Float32Array.copyWithin() (app.js L109) -- O(n) but no allocation, much faster. |
| 37 | **Water shimmer animation** | YES | NO | A animates water opacity with a sine wave (app.js L492-494). Pure aesthetic, but adds life to the scene. |
| 38 | **Vessel mast detail** | YES | NO | A adds a thin cylinder mast on top of the cabin (app.js L177-181). Extra visual detail. |
| 39 | **Vessel heading rotation** | YES | YES | A: `rotation.y = -(heading * PI / 180)` (app.js L272). B: `rotation.y = degToRad(heading)` (app.js L252). Note: A negates the heading. Depending on the cone's default orientation, one may be correct and the other inverted. Both rotate the cone which was pre-roted to point +Z (north). |

---

## Bugs Found

### Implementation A (Claude)

1. **Track line shift() memory leak pattern (app.js L276-278):** Uses `state.trackPositions.shift()` which is O(n) on every position update and generates garbage. For 500 points at 1Hz this is tolerable, but at higher update rates it degrades.

2. **No camera re-targeting:** The camera is placed at a fixed position (50, 60, 80) and never moves to follow the vessel. As the vessel moves away from the ENU origin, it will exit the camera's view. The user must manually pan to find it. This is a **significant UX issue** for a live tracking viewer.

3. **No `frustumCulled = false` on bathymetry/track:** Three.js computes bounding spheres lazily. For dynamically growing point clouds, this can cause the entire cloud to be culled (invisible) until the bounding sphere catches up. B explicitly disables frustum culling.

4. **Depth quality CSS class mismatch (minor):** The code sets `quality-fair` via the quality enum value "fair" (app.js L351), but the CSS defines `.quality-warning` (style.css L175). The schema uses "fair" not "warning" so this means fair-quality depth readings get no color styling. The class `quality-fair` does not exist in the CSS.

5. **Bathymetry accumulation is append-only (app.js L299-339):** Each snapshot's cells are appended starting from the current count. If the twin sends overlapping viewports (which it will -- the viewport follows the vessel), the same cells will be added as duplicate points. B has the same issue. Neither deduplicates.

6. **`socketserver.TCPServer` (serve.py L58):** Single-threaded -- will block on slow transfers. When the browser requests index.html, style.css, and app.js simultaneously, requests serialize.

### Implementation B (Kimi)

1. **Session timer starts at page load, not at connection (app.js L160):** `const sessionStart = Date.now()` runs immediately. If the twin is down for 30 seconds before connecting, the session timer shows 00:30 even though there was no active session. Minor semantic difference.

2. **Bathymetry accumulation is append-only (app.js L261-269):** Same as A -- duplicates cells from overlapping viewports.

3. **No reconnect overlay (minor):** Only updates sidebar text. On a large iPad in bright sunlight, a full-screen overlay (as A has) is more visible.

4. **Channel name parsing is fragile (app.js L198):** `name.replace(/_[a-z]+$/i, '').replace(/_/g, ' ')` turns "sea_temp_c" into "sea temp" (strips the trailing "c" unit suffix). The unit is extracted separately but the channel display name loses meaningful info. A uses a curated label map.

5. **No explicit `controls.minDistance` / `controls.maxDistance`:** A sets these (app.js L101-102). B does not, so the user can zoom into the vessel mesh or fly infinitely far away.

---

## Performance Comparison

| Aspect | A (Claude) | B (Kimi) | Winner |
|---|---|---|---|
| **BufferGeometry pre-allocation** | 50,000 points | 200,000 points | Tie (both pre-allocate) |
| **Track buffer management** | JS array + shift() (GC pressure) | Float32Array.copyWithin (zero alloc) | **B** |
| **Point cloud frustum culling** | Default (may cause flicker) | Explicitly disabled | **B** |
| **HTTP server** | Single-threaded TCPServer | ThreadingTCPServer | **B** |
| **Render loop** | requestAnimationFrame | setAnimationLoop (cleaner) | **B** (slightly) |
| **Bathymetry dedup** | None | None | Tie (both lack it) |

---

## Visual Quality Comparison

| Aspect | A (Claude) | B (Kimi) |
|---|---|---|
| **Dark nautical theme** | Deep navy (#0a1628), well-structured with CSS vars | Dark navy (#06121f), gradient backgrounds, panel cards |
| **Sidebar polish** | Channel cards with hover states, custom scrollbar, footer | Panel-based layout with rounded corners, cleaner typography |
| **Depth readout size** | 48px, thin weight (200) | 52px, bold (700) |
| **Water plane** | Basic material, animated shimmer | Phong material with shininess (more realistic reflections) |
| **Vessel detail** | Hull + cabin + mast (3 parts) | Hull + cabin (2 parts), 12-segment cone (smoother) |
| **Reconnect overlay** | Full-screen blur with spinner | Sidebar text only |
| **Status dot** | Pulsing animation on connecting state | Glow shadow on all states |
| **Responsive design** | 3 breakpoints (portrait, landscape, small) | 2 breakpoints (portrait, narrow landscape) |

A has more visual polish (overlay, mast, shimmer, hover states). B has cleaner material choices (Phong water) and better typography.

---

## Overall Verdict

### Winner: Implementation B (Kimi)

B wins on the criteria that matter most for a production viewer:

1. **Camera follows the vessel (app.js L255-259).** This is the single most important UX feature. A's camera stays at the origin and the vessel sails out of view. This alone makes B the better viewer.

2. **`frustumCulled = false` on dynamic geometry.** Without this, the bathymetry cloud and track line can randomly disappear as Three.js's bounding sphere computation lags behind the growing point count. This is a well-known Three.js gotcha that B handles correctly.

3. **ThreadingTCPServer with Cache-Control: no-store.** B's serve.py is more robust for real browser usage. Concurrent module/CSS/JS fetches work correctly, and the no-cache header prevents the common "I changed app.js but the browser cached the old one" problem during development.

4. **Efficient track ring buffer.** `Float32Array.copyWithin()` is the idiomatic way to manage a fixed-size ring buffer in WebGL applications. A's `array.shift()` is a JavaScript anti-pattern for hot paths.

5. **Import map pattern.** The import map in index.html is the modern Three.js recommended pattern, making version upgrades trivial.

6. **Payload is 38% smaller** (19.9 KB vs 32.0 KB) while delivering the same feature set.

**A's advantages (overlay UI, mast, shimmer, hover states, curated channel labels, explicit zoom limits) are real but secondary to the camera-follow and frustum-culling bugs in B's competitor.**

---

## Harvest List (from the loser -- Implementation A)

These patterns from A should be ported into B:

1. **Full-screen reconnect overlay with spinner (A: index.html L61-66, style.css L278-318):** Much better UX on an iPad in bright conditions. The blur + spinner + countdown is worth the ~40 lines of CSS.

2. **Explicit `controls.minDistance` and `controls.maxDistance` (A: app.js L101-102):** Prevents the user from zooming inside the vessel or flying to infinity. One line to add.

3. **Curated channel label + unit map (A: app.js L393-421):** "Sea Temp" with unit "C" is friendlier than "sea temp" with unit "c". A small lookup table for known channels elevates the UI.

4. **Vessel mast detail (A: app.js L177-181):** A thin cylinder mast makes the vessel silhouette more recognizable from above. Minimal code, real visual benefit.

5. **Water shimmer animation (A: app.js L492-494):** Subtle sine-wave opacity modulation on the water plane. Cheap to compute, adds life to the scene.

6. **Session timer starts on connect (A: app.js L521-523):** More correct semantics -- "session" should mean "connected session", not "page open time".

7. **Three responsive breakpoints (A: style.css L339-413):** A handles portrait iPad, landscape iPad, AND small phones. B only handles portrait + narrow landscape.

---

## Summary

Implementation B (Kimi) is the winner. It is more compact (20 KB vs 32 KB), handles two critical Three.js correctness issues that A misses (camera follow + frustum culling), uses more efficient buffer management, and has a more robust dev server. Implementation A (Claude) has better UI polish (reconnect overlay, mast, shimmer, curated labels) and those patterns are worth harvesting into B.
