"""2.5D Terrain surface mesh reconstruction engine.

Reconstructs a solid, continuous 2.5D Digital Surface Model (TIN mesh) from
sparse or dense point clouds.  This is ideal for nadir/terrain drone flights
where 3D Delaunay volumetric carving (OpenMVS ReconstructMesh) may struggle
with single-viewpoint parallax or produce airborne floaters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import scipy.spatial
import trimesh
from PIL import Image

if TYPE_CHECKING:
    from .workspace import RunWorkspace


# A ground plane recovered from a georeferenced cloud cannot be steeply tilted:
# UTM +Z *is* up by construction, so anything beyond a modest slope means the
# fit locked onto facades or floaters rather than the ground.  15 deg is well
# past any real terrain gradient a survey flight covers and far short of the
# 60-85 deg the unconstrained PCA fit was producing.
MAX_GROUND_TILT_DEG = 15.0


@dataclass(frozen=True)
class GroundPlane:
    """A measured ground plane, with the evidence for trusting it.

    ``rotation`` maps world coordinates into a frame whose +Z is the plane
    normal, so the 2.5D grid can be laid out in the plane.  The remaining
    fields exist so a caller can tell a fit that *worked* from one that was
    rejected -- the previous version returned only the rotation, and a rotation
    is equally well-formed whether it is right or 70 degrees wrong.
    """

    center: np.ndarray
    normal: np.ndarray
    rotation: np.ndarray
    tilt_deg: float
    rms_residual_m: float
    inlier_fraction: float
    source: str  # "fitted" | "prior" | "fit_rejected"


def _rotation_aligning(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Proper rotation (det = +1) taking unit ``source`` onto unit ``target``.

    The antiparallel case matters here.  The previous implementation returned
    ``-np.eye(3)`` for it, which is a *reflection*: determinant -1, so it
    mirrors the scene and inverts every face winding.  A 180 deg rotation about
    any axis perpendicular to ``source`` is the correct answer and keeps the
    handedness of the mesh intact.
    """
    v = np.cross(source, target)
    c = float(np.dot(source, target))
    s = float(np.linalg.norm(v))

    if s < 1e-8:
        if c > 0:
            return np.eye(3)
        # Antiparallel: rotate 180 deg about any perpendicular axis.
        axis = np.array([1.0, 0.0, 0.0])
        if abs(source[0]) > 0.9:
            axis = np.array([0.0, 1.0, 0.0])
        axis = np.cross(source, axis)
        axis /= np.linalg.norm(axis)
        return 2.0 * np.outer(axis, axis) - np.eye(3)

    kmat = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + kmat + (kmat @ kmat) * ((1.0 - c) / (s**2))


def fit_ground_plane(
    points: np.ndarray,
    up_hint: np.ndarray | None = None,
    max_tilt_deg: float = MAX_GROUND_TILT_DEG,
) -> GroundPlane:
    """Recover the ground plane of a dense cloud, robustly and measurably.

    The plane that PCA finds is the axis of least variance of *every* point,
    and in an urban dense cloud that is not the ground.  Building facades,
    vegetation and reconstruction floaters all contribute variance along the
    vertical, and on a single-pass orbit the horizontal footprint is narrow in
    one direction, so the least-variance axis routinely comes out nearly
    horizontal.  Measured on the runs in this repository, the old fit reported
    ground normals tilted 60-85 deg from vertical on five of the six real
    scenes -- ``fixture_orbit_hires`` at 59.9 deg, ``fixture_corridor_v1`` at
    70.5 deg -- which is why the 2.5D product came out on a plane that had
    nothing to do with the ground.  Rotating a scene by that much collapses its
    true height: the corridor's 228 m of relief became 22 m of "elevation" in
    the rotated frame.

    Two further defects made it worse.  The eigenvector's sign is arbitrary, so
    the normal pointed *down* on four runs, inverting the surface -- buildings
    became pits.  And the antiparallel branch returned a reflection rather than
    a rotation, mirroring the mesh.

    This replaces that with three things:

    1.  **A prior.**  In a georeferenced cloud the vertical is known -- UTM +Z
        is up -- so the fit refines a known answer instead of searching for it.
    2.  **A robust estimate.**  The plane is fitted to the *lower envelope*
        (points between the 2nd and 30th height percentiles), which is ground
        by construction, not to the full cloud.  The low tail is excluded so
        sub-surface floaters cannot drag it.
    3.  **A rejection test.**  A fit tilted further than ``max_tilt_deg`` from
        the prior is discarded in favour of the prior, and says so in
        ``source``.  A wrong plane is worse than no plane, and silently
        shipping one is what produced the misaligned product.
    """
    up = np.array([0.0, 0.0, 1.0]) if up_hint is None else np.asarray(up_hint, dtype=float)
    up = up / max(float(np.linalg.norm(up)), 1e-12)

    if len(points) < 16:
        # Too few points to fit anything defensible; use the prior and say so.
        return GroundPlane(
            center=points.mean(axis=0) if len(points) else np.zeros(3),
            normal=up,
            rotation=_rotation_aligning(up, np.array([0.0, 0.0, 1.0])),
            tilt_deg=0.0,
            rms_residual_m=float("nan"),
            inlier_fraction=0.0,
            source="prior",
        )

    normal = up.copy()
    center = np.median(points, axis=0)
    band = points

    # Three passes is enough: the height ordering barely changes once the
    # normal is within a few degrees, and more iterations only re-fit noise.
    for _ in range(3):
        height = (points - center) @ normal
        lo, hi = np.percentile(height, [2.0, 30.0])
        band = points[(height >= lo) & (height <= hi)]
        if len(band) < 16:
            band = points
            break
        center = band.mean(axis=0)
        centred = band - center
        cov = centred.T @ centred / len(band)
        evals, evecs = np.linalg.eigh(cov)
        candidate = evecs[:, 0]
        candidate /= max(float(np.linalg.norm(candidate)), 1e-12)
        # Resolve the eigenvector's arbitrary sign against the prior.
        if float(np.dot(candidate, up)) < 0.0:
            candidate = -candidate
        normal = candidate

    tilt = math.degrees(math.acos(float(np.clip(np.dot(normal, up), -1.0, 1.0))))
    source = "fitted"
    if not np.isfinite(tilt) or tilt > max_tilt_deg:
        normal = up
        center = band.mean(axis=0) if len(band) else points.mean(axis=0)
        source = "fit_rejected"
        tilt = 0.0

    residual = (band - center) @ normal
    rms = float(np.sqrt(np.mean(residual**2))) if len(band) else float("nan")
    # "Inlier" is relative to the spread of the band itself, so the number
    # means the same thing on a flat airfield and on a sloping hillside.
    tol = max(3.0 * rms, 0.05) if np.isfinite(rms) else np.inf
    inliers = float(np.mean(np.abs(residual) <= tol)) if len(band) else 0.0

    return GroundPlane(
        center=center,
        normal=normal,
        rotation=_rotation_aligning(normal, np.array([0.0, 0.0, 1.0])),
        tilt_deg=float(tilt),
        rms_residual_m=rms,
        inlier_fraction=round(inliers, 4),
        source=source,
    )


def _fit_ground_plane(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Backwards-compatible 3-tuple wrapper around :func:`fit_ground_plane`."""
    plane = fit_ground_plane(points)
    return plane.center, plane.normal, plane.rotation


def up_hint_from_cameras(images_txt: Path) -> np.ndarray | None:
    """Derive the vertical from where the cameras were looking.

    Without telemetry, COLMAP's world frame is arbitrary: its +Z has no
    relation to gravity, so defaulting the ground-plane prior to +Z is a guess
    dressed up as a prior.  But the poses themselves carry the information.  A
    survey flight points its camera at the ground, so the mean optical axis is
    a good estimate of *down*, and its negation of up.

    This is weaker than telemetry and is not a substitute for it: an orbit that
    tilts the gimbal to 45 degrees biases the estimate by roughly that much.
    It is used only as the prior a fit is measured against, and the fit is
    still allowed to reject it.  Returns ``None`` when the poses cannot be
    read or disagree with each other too much to mean anything -- which is a
    distinct outcome from "up is +Z".
    """
    if not images_txt.exists():
        images_txt = images_txt.parent / "txt" / "images.txt"
    if not images_txt.exists():
        return None

    axes: list[np.ndarray] = []
    try:
        with images_txt.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split()
                # IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME; the alternating
                # POINTS2D lines have no 10th token that looks like a filename.
                if len(parts) < 10 or "." not in parts[9]:
                    continue
                qw, qx, qy, qz = (float(v) for v in parts[1:5])
                n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
                if n < 1e-9:
                    continue
                qw, qx, qy, qz = qw / n, qx / n, qy / n, qz / n
                # Third row of R (world->camera) transposed is R^T @ [0,0,1]:
                # the camera's viewing direction expressed in world coordinates.
                axes.append(np.array([
                    2.0 * (qx * qz + qw * qy),
                    2.0 * (qy * qz - qw * qx),
                    1.0 - 2.0 * (qx * qx + qy * qy),
                ]))
    except Exception:
        return None

    if len(axes) < 3:
        return None

    stacked = np.asarray(axes)
    mean_axis = stacked.mean(axis=0)
    norm = float(np.linalg.norm(mean_axis))
    # A norm near zero means the views cancel out -- cameras pointing every
    # which way, so there is no consistent "down" to extract.  0.5 keeps an
    # orbit with a 60 deg spread and discards a genuinely incoherent set.
    if norm < 0.5:
        return None
    return -mean_axis / norm


def reconstruct_terrain_mesh(
    points: np.ndarray,
    colors: np.ndarray,
    output_obj: Path,
    output_ply: Path | None = None,
    grid_dim: int = 250,
    max_grid_dim: int = 400,
    k_neighbors: int = 6,
    up_hint: np.ndarray | None = None,
    max_tilt_deg: float = MAX_GROUND_TILT_DEG,
) -> dict[str, int | float | str]:
    """Build a continuous 2.5D terrain surface mesh from 3D points.

    Args:
        points: (N, 3) float array of XYZ points
        colors: (N, 3) uint8 array of RGB colors
        output_obj: Destination path for OBJ file (with .mtl and texture)
        output_ply: Optional destination path for PLY file
        grid_dim: Target grid resolution along the primary axis
        max_grid_dim: Maximum grid resolution clamp
        k_neighbors: Number of nearest neighbors for inverse distance weighting
        up_hint: Known vertical direction, when the cloud is georeferenced.
            Defaults to +Z, which is correct for UTM and local-ENU clouds.
        max_tilt_deg: Reject a fitted plane tilted further than this from
            ``up_hint`` and fall back to the hint.  See :func:`fit_ground_plane`.

    Returns:
        Dictionary of mesh metrics, including the ground-plane measurements
        (``ground_tilt_deg``, ``ground_plane_source``, ...) so a misaligned
        product is visible in the manifest rather than only in the viewer.
    """
    if len(points) < 10:
        raise RuntimeError(f"Cannot reconstruct terrain mesh: only {len(points)} points available.")

    output_obj.parent.mkdir(parents=True, exist_ok=True)

    # 1. Fit ground plane and rotate into canonical horizontal coordinates
    plane = fit_ground_plane(points, up_hint=up_hint, max_tilt_deg=max_tilt_deg)
    center, R = plane.center, plane.rotation
    pts_rot = (points - center) @ R.T

    # 2. Compute 2D bounding box with 1st-99th percentile trimming to suppress outliers
    x_min, x_max = float(np.percentile(pts_rot[:, 0], 0.5)), float(np.percentile(pts_rot[:, 0], 99.5))
    y_min, y_max = float(np.percentile(pts_rot[:, 1], 0.5)), float(np.percentile(pts_rot[:, 1], 99.5))

    dx = max(x_max - x_min, 1e-3)
    dy = max(y_max - y_min, 1e-3)

    aspect = dy / dx
    if aspect >= 1.0:
        ny = min(max_grid_dim, max(40, int(grid_dim * aspect)))
        nx = min(max_grid_dim, max(40, int(grid_dim)))
    else:
        nx = min(max_grid_dim, max(40, int(grid_dim / aspect)))
        ny = min(max_grid_dim, max(40, int(grid_dim)))

    xi = np.linspace(x_min, x_max, nx)
    yi = np.linspace(y_min, y_max, ny)
    GX, GY = np.meshgrid(xi, yi)
    grid_xy = np.column_stack([GX.ravel(), GY.ravel()])

    # 3. Fast KDTree Inverse Distance Weighting for elevation and RGB colors
    tree = scipy.spatial.cKDTree(pts_rot[:, :2])
    k_query = min(k_neighbors, len(points))
    dists, idxs = tree.query(grid_xy, k=k_query)

    # Handle k=1 1D array shape from cKDTree
    if k_query == 1:
        dists = dists[:, None]
        idxs = idxs[:, None]

    weights = 1.0 / np.maximum(dists, 1e-4)**2
    weights /= weights.sum(axis=1, keepdims=True)

    gz = np.sum(weights * pts_rot[idxs, 2], axis=1)

    if colors is not None and len(colors) == len(points):
        gr = np.clip(np.sum(weights * colors[idxs, 0], axis=1), 0, 255).astype(np.uint8)
        gg = np.clip(np.sum(weights * colors[idxs, 1], axis=1), 0, 255).astype(np.uint8)
        gb = np.clip(np.sum(weights * colors[idxs, 2], axis=1), 0, 255).astype(np.uint8)
    else:
        gr = np.full(len(gz), 180, dtype=np.uint8)
        gg = np.full(len(gz), 180, dtype=np.uint8)
        gb = np.full(len(gz), 180, dtype=np.uint8)

    # 4. Transform grid vertices back to original 3D coordinates
    V_rot = np.column_stack([grid_xy, gz])
    V_orig = V_rot @ R + center

    # 5. Build regular 2.5D surface triangulation
    faces = []
    for r in range(ny - 1):
        for c in range(nx - 1):
            i0 = r * nx + c
            i1 = r * nx + (c + 1)
            i2 = (r + 1) * nx + c
            i3 = (r + 1) * nx + (c + 1)
            faces.append([i0, i1, i2])
            faces.append([i1, i3, i2])
    faces_arr = np.array(faces, dtype=np.int32)

    # 6. Build UV mapping and texture atlas
    u = (GX.ravel() - x_min) / dx
    v = (GY.ravel() - y_min) / dy
    uv = np.column_stack([u, v])

    tex_img = np.column_stack([gr, gg, gb]).reshape((ny, nx, 3))
    # Flip vertically so row 0 corresponds to y_max (top of image, v=1),
    # matching the OBJ/glTF convention where v=0 is y_min (bottom of image).
    tex_img = np.flipud(tex_img)
    pil_img = Image.fromarray(tex_img)
    visual = trimesh.visual.TextureVisuals(uv=uv, image=pil_img)

    mesh = trimesh.Trimesh(vertices=V_orig, faces=faces_arr, visual=visual, process=False)

    # 7. Export OBJ + MTL + Texture
    obj_str, files = trimesh.exchange.obj.export_obj(mesh, return_texture=True)
    output_obj.write_text(obj_str, encoding="utf-8")
    for filename, content in files.items():
        file_path = output_obj.parent / filename
        if filename.endswith(".mtl"):
            # Ensure full diffuse reflectance (Kd 1.0) so glTF export does not dim by 60%
            if isinstance(content, bytes):
                content = content.replace(
                    b"Kd 0.40000000 0.40000000 0.40000000",
                    b"Kd 1.00000000 1.00000000 1.00000000",
                )
            elif isinstance(content, str):
                content = content.replace(
                    "Kd 0.40000000 0.40000000 0.40000000",
                    "Kd 1.00000000 1.00000000 1.00000000",
                )
        if isinstance(content, str):
            file_path.write_text(content, encoding="utf-8")
        else:
            file_path.write_bytes(content)

    if output_ply is not None:
        mesh.export(str(output_ply))

    return {
        "n_vertices": len(mesh.vertices),
        "n_faces": len(mesh.faces),
        "grid_nx": nx,
        "grid_ny": ny,
        "ground_tilt_deg": round(plane.tilt_deg, 3),
        "ground_plane_source": plane.source,
        "ground_rms_residual_m": (
            round(plane.rms_residual_m, 4) if np.isfinite(plane.rms_residual_m) else None
        ),
        "ground_inlier_fraction": plane.inlier_fraction,
        # Relief measured in the *aligned* frame. If this is wildly smaller
        # than the cloud's own Z span, the plane is still wrong: that is the
        # signature the old fit left behind (corridor 228 m -> 22 m).
        "relief_m": round(float(pts_rot[:, 2].max() - pts_rot[:, 2].min()), 3),
        "cloud_z_span_m": round(float(points[:, 2].max() - points[:, 2].min()), 3),
    }
