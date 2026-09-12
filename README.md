# dronemap — SIH26158

**Single-Pass Drone Video → Accurate, Georeferenced 3D Model**
Smart India Hackathon 2026 · Problem Statement **SIH26158** · Problem owner: **NTRO**

Turns one continuous drone video pass (plus whatever GPS/flight telemetry is available)
into a georeferenced, metrically scaled, textured 3D model — terrain, buildings, roads,
vegetation — with a measurement viewer and an accuracy report.

---

## Design principle: Guaranteed Core vs. Stretch

Every stage has a **Core** implementation (classical, boring, reliable) and an optional
**Stretch** implementation (the AI-forward differentiator). The Core path
(`Stages 1→2→3→4b→5→6→7`, COLMAP + OpenMVS) is a complete working submission on its own.
Nothing in the Core path depends on a Stretch component succeeding — so a Stretch failure
costs you an enhancement, never the demo.

| Stage | Core (guaranteed) | Stretch |
|---|---|---|
| 1 Preprocessing | sharpness filter + baseline-aware keyframe sampling | — |
| 2 Dynamic masking | YOLOv8-seg | SAM 2 |
| 3 Pose + georeferencing | COLMAP SfM + GNSS priors / Umeyama + `evo` | MASt3R / VGGT |
| 4a Depth | — | Depth Anything V2 / Metric3D v2 |
| 4b Semantics | SegFormer (aerial-domain checkpoint) | PTv3 |
| 5 Dense cloud | OpenMVS `DensifyPointCloud` | 3D Gaussian Splatting (Kaggle) |
| 6 Mesh | OpenMVS `ReconstructMesh`/`Refine`/`Texture` | SuGaR |
| 7 Output | OBJ/GLB/LAZ/GeoTIFF + Three.js measure viewer | live progressive preview |

---

## Setup

Requires Windows + an NVIDIA GPU. No admin rights and no compilation needed.

```bash
python -m pip install uv
python -m uv sync --extra ml --extra geo3d
python -m uv run python scripts/bootstrap.py
python -m uv run dronemap doctor
```

`bootstrap.py` downloads prebuilt **COLMAP** and **OpenMVS** binaries plus the COLMAP
vocabulary tree into `tools/`, then verifies that every CLI flag the pipeline uses actually
exists in the installed build. `dronemap doctor` prints the full environment report.

> **Why Python 3.11 and not newer?** `open3d` and `pycolmap` have no cp314 wheels.
> `uv` installs and pins 3.11 for this project only; your system Python is untouched.

## Usage

```bash
# full Core path
python -m uv run dronemap run --video flight.mp4 --telemetry flight.srt --run-id demo01

# no telemetry available: up-to-scale mode (relative measurements only)
python -m uv run dronemap run --video flight.mp4 --no-telemetry --run-id smoke

# individual stages (all resumable; re-running skips completed stages)
python -m uv run dronemap frames --run-id demo01
python -m uv run dronemap pose   --run-id demo01

# serve the measurement viewer
python -m uv run dronemap serve
```

## Accuracy: read this before claiming anything

Absolute georeferencing accuracy is capped by the **GNSS regime**, not by the vision method:

| GNSS mode | Horizontal | Vertical |
|---|---|---|
| Standalone / consumer geotags | ~1–5 m | several m |
| RTK / PPK onboard | ~1–3 cm | ~3–8 cm |

Every run records its GNSS mode in the accuracy report, and flags it as `SIMULATED` if the
telemetry was synthesised. **Do not claim cm-level accuracy without RTK/PPK data in hand.**
On standalone GNSS, lead with *relative* metric accuracy measured against known-length
reference objects — which is why you must **put 2–3 objects of known length in frame when
you record**. That cannot be fixed after the flight.

Façade reconstruction from a pure nadir pass is physically limited (those surfaces are
barely seen). Present it as a known limitation plus a capture recommendation — add gimbal
obliquity or a cross-strip — not as a bug.

## Reference documents

- `SIH26158_Research_Dossier.md` — the technical survey: state of the art, architecture,
  accuracy budget, datasets, evaluation protocol.
- `SIH26158_Implementation_Plan_v4.md` — the build plan this repo implements.
