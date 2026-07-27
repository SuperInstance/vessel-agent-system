# AELMA Viewer

Browser-based 3D live view for the AELMA digital twin of the **F/V EILEEN**.
Connects to the twin core at `ws://localhost:8090` and renders the vessel,
its track, and progressive bathymetry on a dark nautical UI.

## Quickstart

```bash
# 1. start the twin core (must serve VesselStateSnapshot JSON on ws://localhost:8090)

# 2. serve this directory
cd build_kimi_viewer
python serve.py            # default port 8080
# or: python serve.py --port 9000

# 3. open the viewer
#    Chrome or Safari (iPad):  http://localhost:8080/
```

No build step. The only external dependency is Three.js `0.160.0`, loaded
from the unpkg CDN via an import map in `index.html`.

## Files

| File         | Purpose                                                        |
|--------------|----------------------------------------------------------------|
| `index.html` | Entry point; import map + module bootstrap, sidebar skeleton   |
| `style.css`  | Dark nautical theme, 320 px sidebar, responsive iPad layouts   |
| `app.js`     | WebSocket client, ENU projection, Three.js scene, DOM updates  |
| `serve.py`   | `http.server` with CORS headers (`--port`, default 8080)       |

## Scene notes

- **Coordinates:** local ENU frame anchored at the first received fix;
  1 unit = 1 m (`+x` east, `+y` up, `+z` north per the brief).
- **Vessel:** orange (`#ff7700`) 8 m cone hull + 3 m box cabin, rotated to
  compass heading; orange track line keeps the last 500 positions.
- **Bathymetry:** point cloud colored by depth (warm orange < 30 m,
  green 30–80 m, blue > 80 m) with per-point alpha from confidence.
- **Controls:** OrbitControls — drag to rotate, wheel/pinch to zoom;
  the camera auto-rotates after 5 s of no input and stops on any touch.
- **Sidebar:** vessel id + connection dot, big depth readout colored by
  quality (green/yellow/red), channel grid, voxel count, session timer.
  Values pulse subtly when they update.

## Reconnect behavior

If the twin core drops, the viewer retries with exponential backoff
starting at 250 ms, doubling up to a 5 s cap, and resumes rendering on
reconnect.
