"""Stage 4b — Semantic segmentation with SegFormer.

What this stage does
--------------------
Runs a SegFormer model on every keyframe to produce per-pixel semantic labels.
The stage is **disabled by default** (``semantics.enabled: false``) because a
Cityscapes or ADE20K checkpoint — which is what you get from Hugging Face
without specifying otherwise — is trained on street-level imagery and will
produce garbage predictions on nadir aerial views.  Enable this stage only
after you have verified the checkpoint with UAVid / LoveDA / ISPRS Potsdam data.

Classes emitted by a UAVid-tuned checkpoint (8 classes):
  0 background   1 building     2 road     3 tree
  4 low_veg      5 human        6 vehicle  7 boat/water

If you use an ADE20K checkpoint you will get 150 classes — the output format
still works, but the class names in class_fractions.json will be ADE labels.

Outputs
-------
``ws.stage_dir("semantics")/labels/<stem>.png``  — uint8 label map per frame
``ws.stage_dir("semantics")/class_fractions.json``  — mean class coverage
``ws.stage_dir("semantics")/id2label.json``         — label → class name map
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .config import Config
    from .tools import ToolRegistry
    from .workspace import RunWorkspace, _StageContext


def _load_model(model_name: str):
    """Load SegFormer via Hugging Face Transformers."""
    try:
        from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "transformers and torch are required for semantics. "
            "Run `uv sync --extra ml`."
        ) from exc

    device = "cuda" if __import__("torch").cuda.is_available() else "cpu"
    processor = SegformerImageProcessor.from_pretrained(model_name)
    model = SegformerForSemanticSegmentation.from_pretrained(model_name)
    model.to(device)
    model.eval()
    return processor, model, device


def _predict_batch(processor, model, images_bgr: list[np.ndarray], device: str) -> list[np.ndarray]:
    """Run SegFormer on a batch of BGR images; return list of label maps (uint8, H×W)."""
    import torch

    # Convert BGR → RGB PIL-like
    images_rgb = [cv2.cvtColor(img, cv2.COLOR_BGR2RGB) for img in images_bgr]
    inputs = processor(images=images_rgb, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits  # (B, num_classes, H/4, W/4)
    # Upsample to original size
    h0, w0 = images_bgr[0].shape[:2]
    upsampled = torch.nn.functional.interpolate(
        logits, size=(h0, w0), mode="bilinear", align_corners=False
    )
    label_maps = upsampled.argmax(dim=1).cpu().numpy().astype(np.uint8)
    return list(label_maps)


def run(ws: "RunWorkspace", config: "Config", tools: "ToolRegistry", ctx: "_StageContext") -> None:
    cfg = config.semantics

    if not cfg.checkpoint_domain_verified:
        ctx.note(
            "semantics.checkpoint_domain_verified is False. "
            "This means the checkpoint has NOT been verified on aerial/UAV imagery. "
            "A Cityscapes/ADE checkpoint will produce meaningless labels on nadir views. "
            "Set checkpoint_domain_verified: true in your config only after "
            "testing on UAVid / LoveDA / ISPRS data."
        )
        raise RuntimeError(
            "Stage 'semantics' aborted: checkpoint domain not verified. "
            "See the note above. To skip this stage entirely, set semantics.enabled: false."
        )

    if not ws.frames_index.exists():
        raise RuntimeError("keyframes.json not found — run stage 'frames' first.")
    keyframes = json.loads(ws.frames_index.read_text(encoding="utf-8"))

    sem_dir = ws.stage_dir("semantics")
    labels_dir = sem_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    processor, model, device = _load_model(cfg.model)
    ctx.note(f"SegFormer model: {cfg.model}, device: {device}")

    # Get id2label mapping
    id2label: dict[int, str] = getattr(model.config, "id2label", {})
    (sem_dir / "id2label.json").write_text(
        json.dumps({str(k): v for k, v in id2label.items()}, indent=2), encoding="utf-8"
    )

    # Run inference in batches
    n_classes = model.config.num_labels
    class_pixel_counts = np.zeros(n_classes, dtype=np.int64)
    total_pixels = 0

    batch_images: list[np.ndarray] = []
    batch_stems: list[str] = []

    def _flush_batch() -> None:
        nonlocal total_pixels
        if not batch_images:
            return
        label_maps = _predict_batch(processor, model, batch_images, device)
        for stem, label_map in zip(batch_stems, label_maps):
            cv2.imwrite(str(labels_dir / f"{stem}.png"), label_map)
            for cls_id in range(n_classes):
                class_pixel_counts[cls_id] += int((label_map == cls_id).sum())
            total_pixels += label_map.size
        batch_images.clear()
        batch_stems.clear()

    for kf in keyframes:
        img_path = Path(kf["path"])
        if not img_path.exists():
            continue
        bgr = cv2.imread(str(img_path))
        if bgr is None:
            continue
        batch_images.append(bgr)
        batch_stems.append(img_path.stem)
        if len(batch_images) >= cfg.batch_size:
            _flush_batch()

    _flush_batch()

    # Summarise class coverage
    if total_pixels > 0:
        class_fractions = {
            id2label.get(i, str(i)): round(float(class_pixel_counts[i] / total_pixels), 4)
            for i in range(n_classes)
            if class_pixel_counts[i] > 0
        }
    else:
        class_fractions = {}

    (sem_dir / "class_fractions.json").write_text(
        json.dumps(class_fractions, indent=2), encoding="utf-8"
    )

    ctx.metric(n_frames_segmented=len(keyframes), n_classes=n_classes)
    ctx.output(labels_dir=str(labels_dir))
