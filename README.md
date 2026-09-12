# DroneMap — SIH26158

**Single-Pass Drone Video → Accurate, Georeferenced 3D Model**  
Smart India Hackathon 2026 · Problem Statement **SIH26158** · Problem Owner: **NTRO**

Turns a single continuous drone video flight pass (plus flight telemetry/GPS) into a georeferenced, metrically scaled, photo-textured 3D model — terrain, buildings, roads, vegetation — complete with an interactive WebGL measurement studio and an accuracy report.

---

## Architecture: Guaranteed Core vs. Stretch

Every stage features a **Core** implementation (deterministic, offline-ready, reliable) and an optional **Stretch** implementation (AI/neural enhancement). The Core path (`Stages 1→2→3→3b→5→6→7`, COLMAP + OpenMVS) is a fully self-contained working system.

```
Drone Video (.mp4/.mov) + Telemetry (.srt/.csv)
    │
    ▼
[Stage 1: Frames]    Deblur & baseline-aware keyframe selection
    │
    ▼
[Stage 2: Masks]     Dynamic object removal (YOLOv8-seg)
    │
    ▼
[Stage 3: Pose]      Structure-from-Motion (COLMAP SfM / MASt3R)
    │
    ▼
[Stage 3b: Georef]   Metric scale & geodetic datum alignment (ECEF/ENU)
    │
    ▼
[Stage 5: Dense]     Dense point cloud reconstruction (OpenMVS / 3DGS)
    │
    ▼
[Stage 6: Mesh]      Surface reconstruction & dual texture atlas (OpenMVS)
    │
    ▼
[Stage 7: Export]    OBJ, GLB (Double-sided PBR), LAZ, DSM/DTM, Orthomosaic
    │
    ▼
[Web Studio / API]   In-browser 3D metric measurement & model inspection
```

| Stage | Core (Guaranteed) | Stretch |
|---|---|---|
| **1 Preprocessing** | Sharpness filter + baseline-aware keyframe sampling | — |
| **2 Dynamic Masking** | YOLOv8-seg dynamic entity masking | SAM 2 |
| **3 Pose & SfM** | COLMAP sequential SfM + GPS priors | MASt3R / VGGT |
| **3b Georeferencing** | Metric scale + ECEF/ENU geodetic alignment | RTK/PPK carrier phase |
| **4a Depth / Semantics** | — | Depth Anything V2 / SegFormer |
| **5 Dense Cloud** | OpenMVS `DensifyPointCloud` | 3D Gaussian Splatting (Kaggle) |
| **6 Mesh & Texturing** | OpenMVS `ReconstructMesh` + Texture Atlas (w/ dual seam retry) | 2.5D Terrain Delaunay |
| **7 Deliverables** | GLB, OBJ/MTL, LAZ, GeoTIFF DSM/DTM, Orthomosaic | Live progressive preview |

---

## 💻 Running Locally (Windows / Linux)

### 1. Prerequisites
- **OS**: Windows 10/11 or Ubuntu Linux (x64)
- **GPU**: NVIDIA GPU with CUDA support recommended (CPU mode supported)
- **Python**: Python 3.10 or 3.11 *(Note: Open3D and pycolmap require ≤ 3.11)*

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/Srinjoy-uWu/DroneMap.git
cd DroneMap

# Create and activate a virtual environment
python -m venv .venv

# On Windows:
.\.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# Install DroneMap and dependencies
pip install -e .
```

*(Alternatively, if you use `uv`: `uv sync --extra ml --extra geo3d`)*

### 3. Bootstrap Tools (COLMAP, OpenMVS & Vocab Tree)
Run the automated bootstrap script to download and verify the external binaries into `tools/` (no admin rights or manual compilation needed):
```powershell
python scripts/bootstrap.py
```
Verify your environment:
```powershell
dronemap doctor
```

### 4. Launch the Web Studio
You can start the Web Studio with one click:
- **Windows**: Double-click `launch_studio.bat`, **OR**
- **Terminal**: Run `dronemap serve`

Open your browser at **`http://127.0.0.1:8000`**:
- Click **"+ Process Drone Video"** $\to$ choose your drone video (`.mp4` / `.mov`) $\to$ click **"Start Processing"**.
- View real-time stage progress in the stepper drawer.
- Once finished, view the photorealistic 3D model, switch between Textured/Clay modes, toggle seam-levelled texture variants, and measure 3D real-world distances with point-and-click accuracy.

### 5. CLI Usage
```powershell
# Run the full pipeline on a flight video:
dronemap run --video path/to/flight.mp4 --telemetry path/to/flight.srt --run-id demo01

# No telemetry available (relative scale mode):
dronemap run --video flight.mp4 --no-telemetry --run-id flight_relative

# Run individual stages:
dronemap frames --run-id demo01
dronemap pose   --run-id demo01
dronemap dense  --run-id demo01
dronemap mesh   --run-id demo01
dronemap export --run-id demo01

# Clean scratch, intermediate depth maps (.dmap), or old runs:
dronemap clean --all                       # Safe repo-wide cleanup
dronemap clean --intermediate              # Prune .dmap caches from runs
dronemap clean <run_id>                    # Delete a single specific run
```

---

## ☁️ Running on Kaggle (Free Cloud GPU T4 × 2)

Kaggle provides **30 hours/week of free dual-GPU (NVIDIA T4 × 2)**. You can run DroneMap on Kaggle in two ways:

### Method A: Full Pipeline in a Kaggle Notebook
1. Open [Kaggle](https://www.kaggle.com/) $\to$ **New Notebook**.
2. In the right settings panel:
   - **Accelerator**: Select **GPU T4 × 2**
   - **Internet**: **ON**
3. In the first cell, install dependencies and clone DroneMap:
   ```bash
   # Install COLMAP and FFmpeg via apt
   !apt-get update -qq && apt-get install -y -qq colmap ffmpeg

   # Clone DroneMap repository
   !git clone https://github.com/Srinjoy-uWu/DroneMap.git
   %cd DroneMap

   # Install Python package
   !pip install -e . --quiet
   ```
4. Upload your drone video (or link a Kaggle Dataset) and run:
   ```bash
   !python -m dronemap.cli run --video /kaggle/input/your-dataset/flight.mp4 --profile lowvram
   ```
5. All outputs (`model.glb`, `cloud.laz`, GeoTIFFs, reports) are written to `data/runs/<run_id>/07_export/` ready for download from the notebook file browser.

---

### Method B: Hybrid 3D Gaussian Splatting (3DGS)
The repository contains ready-to-run 3DGS training notebooks under `notebooks/`:
- [`notebooks/3dgs_splatfacto_kaggle.ipynb`](notebooks/3dgs_splatfacto_kaggle.ipynb)
- [`notebooks/sih26158_3dgs_kaggle.py`](notebooks/sih26158_3dgs_kaggle.py)

#### Workflow:
1. **Locally**: Run stages 1–3 (`dronemap frames`, `dronemap pose`) to produce keyframe images and the sparse COLMAP model.
2. **Kaggle**: Upload `03_pose/` and `01_frames/images/` as a private Kaggle Dataset.
3. Open `notebooks/3dgs_splatfacto_kaggle.ipynb` on Kaggle with T4 × 2 GPU $\to$ trains 30,000 iterations in **~25–35 minutes** using `nerfstudio` and `gsplat`.
4. Download the trained `point_cloud.ply` and renders back to your machine.
5. **Locally**: Run `dronemap export --run-id <id>` to package the model into final deliverables.

---

## 🧪 Testing & Verification

The repository includes a comprehensive unit and regression test suite (149 tests):
```powershell
# Run the complete test suite:
pytest -v
```
Tests cover:
- Truthful georeferencing status tiers and coordinate frames
- Ground plane PCA fitting with geodetic vertical priors
- UV-to-texel texture sampling and black-atlas detection
- Automatic mesh repair and component filtering
- Clean command disk pruning safeguards
- Telemetry parsers (DJI SRT and generic CSV)

---

## 📐 Accuracy & Georeferencing Protocol

Absolute georeferencing accuracy is determined by the **GNSS regime**:

| GNSS Mode | Horizontal Accuracy | Vertical Accuracy | Application |
|---|---|---|---|
| **Standalone GNSS** (Consumer drones) | ~1–3 m | ~2–5 m | Site layout, visual inspection |
| **RTK / PPK** (Survey drones) | ~1–3 cm | ~3–8 cm | Cadastral survey, engineering |
| **No Telemetry** | Relative only | Relative only | Scaleless 3D geometry |

Every run records its geodetic coordinate frame in `manifest.json` and `accuracy_report.json`.

---

## 📂 Deliverables Generated per Run

Each run stores its deliverables in `data/runs/<run_id>/07_export/`:
- **`model.glb`**: Self-contained glTF binary with double-sided PBR materials, baked vertex normals, and 8K texture atlas.
- **`model_alt.glb`**: Alternate texture variant (retained when seam-leveling fallback occurs for direct comparison).
- **`cloud.laz`**: Georeferenced dense point cloud (ASPRS LAS 1.4).
- **`dsm.tif`**: Digital Surface Model (GeoTIFF, metric elevations).
- **`dtm.tif`**: Digital Terrain Model (bare-earth GeoTIFF).
- **`orthomosaic.tif`**: Orthorectified true-scale RGB aerial map.
- **`accuracy_report.json` & `report.html`**: Quality metrics, flight geometry assessment, and CRS metadata.
- **`trajectory.kml` / `trajectory.json`**: Recovered 3D flight path.

---

## 📚 Reference Documentation

- [`SIH26158_Research_Dossier.md`](SIH26158_Research_Dossier.md) — Technical survey: photogrammetry vs NeRF/3DGS, error budgets, coordinate frames, and state-of-the-art benchmarks.
- [`SIH26158_5Slide_Official_PPT.md`](SIH26158_5Slide_Official_PPT.md) — Hackathon jury slide deck.
- [`SIH26158_PPT_Presentation_Guide.md`](SIH26158_PPT_Presentation_Guide.md) — Presentation script and speaker notes.

