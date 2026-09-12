"""
SIH26158 — 3D Gaussian Splatting on Kaggle (T4 × 2 GPU)
=========================================================

Run this notebook on Kaggle with the T4 x2 accelerator (30 hr/week/account).
Team members can use 3–4 accounts to get 90–120 hrs total per week.

Workflow
--------
1.  Upload your run's ``03_pose/`` (sparse model) and ``01_frames/images/``
    to Kaggle Datasets.
2.  This notebook installs Nerfstudio, converts the COLMAP model,
    trains a Gaussian Splat, and exports:
    - ``point_cloud/iteration_30000/point_cloud.ply``  — trained 3DGS
    - ``renders/``  — 360° spiral render frames
3.  Download the PLY and renders, put them in your run directory,
    then run ``dronemap export --run-id <id>`` locally to merge them into
    the final deliverable package.

Expected training time (T4 x2, 30 000 iterations):
  ~25–35 min for ≤ 300 keyframes.
  ~50–70 min for 300–600 keyframes.

Kaggle account rotation:
  Account A → Train splat (25 min), download, idle (rest of 12-hr session)
  Account B → Quality render + mesh export
  Account C → Emergency re-train if A's result has artefacts
"""

# ============================================================
# Cell 1 — Environment check
# ============================================================

import subprocess, sys, os
from pathlib import Path

def run(cmd, **kw):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if result.returncode != 0:
        print("STDERR:", result.stderr[-2000:])
        raise RuntimeError(f"Command failed: {cmd}")
    return result.stdout.strip()

# Check GPU
print(run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"))
print("Python:", sys.version)
print("Working dir:", os.getcwd())

# ============================================================
# Cell 2 — Install Nerfstudio + dependencies
# ============================================================

# Install takes ~3-4 min on Kaggle T4
run("pip install nerfstudio==1.1.4 --quiet")
run("pip install gsplat==1.3.0 --quiet")     # fast 3DGS CUDA kernels

# Verify ns-train is available
print(run("ns-train --help | head -5"))

# ============================================================
# Cell 3 — Configuration: set your paths here
# ============================================================

# ── EDIT THESE ───────────────────────────────────────────────────────────────
KAGGLE_DATASET_PATH = "/kaggle/input/sih26158-run/demo01"   # your dataset path
RUN_ID = "demo01"
N_ITERATIONS = 30_000     # 7 000 for quick test, 30 000 for full quality
EVAL_EVERY   = 2_000      # render a test view every N iters
# ─────────────────────────────────────────────────────────────────────────────

IMAGES_DIR = Path(KAGGLE_DATASET_PATH) / "01_frames" / "images"
COLMAP_DIR = Path(KAGGLE_DATASET_PATH) / "03_pose"
OUT_DIR    = Path(f"/kaggle/working/{RUN_ID}_splat")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"Images:     {IMAGES_DIR} ({len(list(IMAGES_DIR.glob('*.jpg')))} images)")
print(f"COLMAP:     {COLMAP_DIR}")
print(f"Output:     {OUT_DIR}")

# ============================================================
# Cell 4 — Convert COLMAP model to Nerfstudio format
# ============================================================

# Nerfstudio's `ns-process-data` converts a COLMAP sparse model
# and images into the transforms.json format it expects.

ns_data_dir = OUT_DIR / "ns_data"
ns_data_dir.mkdir(exist_ok=True)

run(
    f"ns-process-data images "
    f"  --data {IMAGES_DIR} "
    f"  --output-dir {ns_data_dir} "
    f"  --colmap-model-path {COLMAP_DIR}/0 "
    f"  --skip-colmap "           # we already have a COLMAP model
    f"  --matching-method exhaustive"
)

print("transforms.json:", (ns_data_dir / "transforms.json").exists())

# ============================================================
# Cell 5 — Train 3D Gaussian Splat
# ============================================================

# splatfacto: Nerfstudio's 3DGS implementation
# --pipeline.datamanager.train-num-images-to-sample-from: how many images to
#   use per step (all by default; reduce if OOM on small GPU)

splat_output_dir = OUT_DIR / "splat_train"

train_cmd = (
    f"ns-train splatfacto "
    f"  --data {ns_data_dir} "
    f"  --output-dir {splat_output_dir} "
    f"  --experiment-name {RUN_ID} "
    f"  --max-num-iterations {N_ITERATIONS} "
    f"  --pipeline.model.cull-alpha-thresh 0.005 "
    f"  --pipeline.model.continue-cull-post-densification False "
    f"  --vis wandb "           # remove if you don't have wandb
    f"  nerfstudio-data "
    f"  --data {ns_data_dir} "
)

print("Training command:", train_cmd[:200], "...")
run(train_cmd)

# ============================================================
# Cell 6 — Export the Gaussian splat as PLY
# ============================================================

# Find the latest checkpoint
import glob
ckpts = sorted(glob.glob(str(splat_output_dir / "**" / "*.ckpt"), recursive=True))
latest_ckpt = ckpts[-1] if ckpts else None
print("Latest checkpoint:", latest_ckpt)

ply_out = OUT_DIR / f"{RUN_ID}_splat.ply"

if latest_ckpt:
    run(
        f"ns-export gaussian-splat "
        f"  --load-config {Path(latest_ckpt).parent.parent / 'config.yml'} "
        f"  --output-dir {OUT_DIR} "
    )
    print("PLY exported:", ply_out.exists())

# ============================================================
# Cell 7 — Render a 360° spiral video
# ============================================================

render_dir = OUT_DIR / "renders"
render_dir.mkdir(exist_ok=True)

if latest_ckpt:
    run(
        f"ns-render camera-path "
        f"  --load-config {Path(latest_ckpt).parent.parent / 'config.yml'} "
        f"  --output-path {render_dir}/spiral.mp4 "
        f"  --rendered-output-names rgb "
        f"  --camera-path-filename {ns_data_dir}/camera_path.json "
    )

# ============================================================
# Cell 8 — Package outputs for download
# ============================================================

import shutil, zipfile

zip_path = f"/kaggle/working/{RUN_ID}_splat_outputs.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    # PLY
    for f in OUT_DIR.glob("*.ply"):
        zf.write(f, f.name)
    # Renders
    for f in render_dir.glob("*"):
        zf.write(f, f"renders/{f.name}")
    # Config (for reproducibility)
    for f in splat_output_dir.glob("**/config.yml", recursive=True):  # type: ignore
        zf.write(f, f"train_config/{f.name}")
        break

zip_size_mb = Path(zip_path).stat().st_size / 1e6
print(f"\nOutput zip: {zip_path} ({zip_size_mb:.1f} MB)")
print("\nDownload this file from Kaggle output → add to your run's 05b_splat/ folder")
print(f"Then run: dronemap export --run-id {RUN_ID}")

# ============================================================
# Cell 9 — Quality metrics
# ============================================================

# PSNR / SSIM on held-out views (Nerfstudio computes these during training)
metrics_files = sorted(OUT_DIR.glob("**/metrics.json", recursive=True))  # type: ignore
if metrics_files:
    import json
    m = json.loads(metrics_files[-1].read_text())
    print("\nFinal training metrics:")
    for k in ("psnr", "ssim", "lpips"):
        if k in m:
            print(f"  {k}: {m[k]:.4f}")
else:
    print("No metrics.json found — check training completed successfully")

print("\nDone. Download the zip from Kaggle → Output tab.")
