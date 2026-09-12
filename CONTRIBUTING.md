# Contributing to DroneMap

Thank you for your interest in contributing to **DroneMap**! DroneMap is an open-source, single-pass aerial photogrammetry suite designed to reconstruct high-fidelity, metrically accurate 3D models and GIS deliverables from drone video captures.

---

## 1. Branching Strategy

DroneMap follows a structured Git workflow to maintain release stability while facilitating collaborative feature development:

- **`main`**: The stable release branch. Code here is verified, passes all automated tests, and serves tested models. Pull requests to `main` come from `develop` or release branches.
- **`develop`**: The primary integration branch. All feature branches and bug fixes are merged here first before release tagging.
- **`feature/<feature-name>`**: Branched from `develop`. Used for new capabilities, algorithms, or stage implementations.
- **`fix/<issue-name>`**: Branched from `develop` (or `main` for hotfixes). Used for bug fixes, performance optimizations, or edge-case handling.

---

## 2. Architecture Overview

DroneMap uses a canonical sequential 7-stage processing pipeline:

```
frames (Stage 1) -> masks (Stage 2) -> pose (Stage 3) -> georef (Stage 3b) -> dense (Stage 5) -> mesh (Stage 6) -> export (Stage 7)
```

Each stage is defined by a `StageSpec` in `src/dronemap/pipeline.py` and records its status, execution time, metrics, and artifact outputs in `manifest.json`.

---

## 3. Development Setup

### Prerequisites
- **Python**: 3.11 or higher
- **OS**: Windows 10/11, Linux (Ubuntu 22.04+), or macOS
- **Hardware**: 8 GB RAM minimum (16 GB+ recommended). CUDA-enabled NVIDIA GPU recommended for accelerated COLMAP and OpenMVS runs.

### Environment Installation
```bash
git clone https://github.com/Srinjoy-uWu/DroneMap.git
cd DroneMap

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\activate      # Windows PowerShell
# source .venv/bin/activate   # Linux / macOS

# Install package in editable mode with development dependencies
pip install -e ".[dev]"
```

### External Tool Binaries
DroneMap orchestrates COLMAP, OpenMVS, and FFmpeg:
```powershell
python scripts/bootstrap.py
dronemap doctor
```

---

## 4. Running Tests & Quality Verification

Before opening a pull request, verify that all unit tests and regression guards pass:

```powershell
# Run the complete test suite
python -m pytest -v

# Run with coverage report
python -m pytest --cov=dronemap --cov-report=term-missing
```

### Key Safety Invariants
1. **Never Commit Data / Run Caches**: Large point clouds, `.ply`, `.mvs`, `.dmap`, `.glb`, and video files must never be committed to Git. Ensure `.gitignore` is strictly respected.
2. **Deterministic Coordinate Conversions**: Any changes to georeferencing or vertical datum handling must preserve local ENU metric distances and invertible ECEF transformations.
3. **PBR Material Standards**: Exported GLBs must always have `doubleSided: true` and `metallicFactor: 0.0` (handled in Stage 7) so they render photorealistically in WebGL viewers.

---

## 5. Local Web Studio Testing

To test changes to the FastAPI backend or Three.js interactive viewer:

```powershell
python -m uvicorn dronemap.api.server:app --host 127.0.0.1 --port 8000 --reload
```
Open http://127.0.0.1:8000 in your browser.

---

## 6. Submitting Pull Requests

1. Create a feature branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/my-enhancement
   ```
2. Make atomic, well-documented commits:
   ```bash
   git commit -m "feat(stage6): add adaptive TIN decimation for large terrain surfaces"
   ```
3. Push to your fork or origin branch:
   ```bash
   git push origin feature/my-enhancement
   ```
4. Open a Pull Request targeting `develop` on GitHub.
