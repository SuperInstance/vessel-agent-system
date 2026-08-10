# schema/ — JSON Schemas and Design Briefs

> *The contracts. Every wire format, every data structure, every agreement between components.*

## Files

| File | Description |
|------|-------------|
| [`telemetry_packet.schema.json`](telemetry_packet.schema.json) | Schema for telemetry packets — the wire format between bridge and twin. |
| [`vessel_state.schema.json`](vessel_state.schema.json) | Schema for vessel state snapshots — the wire format between twin and viewer. |
| [`bathymetry_voxel.schema.json`](bathymetry_voxel.schema.json) | Schema for bathymetry voxels — spatial depth data. |
| [`actions.py`](actions.py) | Action type definitions for watcher-fired events. |
| [`validator.py`](validator.py) | Schema validation utilities. |
| [`shared_brief.md`](shared_brief.md) | Shared component design brief. |
| [`shared_sim_brief.md`](shared_sim_brief.md) | Simulator design brief. |
| [`shared_twin_brief.md`](shared_twin_brief.md) | Twin core design brief. |
| [`shared_viewer_brief.md`](shared_viewer_brief.md) | Viewer design brief. |

## Why JSON Schema?

The air-gap principle means no external schema registries. JSON Schema is human-readable, version-portable, and validateable with pure stdlib. Every component can be independently replaced as long as it honors the schema.

---

[← Back to AELMA](../README.md) | [← Vessel Agent System](../../README.md)
