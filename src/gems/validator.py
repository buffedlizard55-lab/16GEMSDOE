"""Strict GeoTIFF submission validator and writer for DOE GEMS Prize (DrivenData #306).

Prevents the "Predicted values must be in range [0, 1]" server rejection by enforcing:
1. Exact grid alignment with sample_submission.tif:
   - CRS: EPSG:32611
   - Shape: (3730, 3292)
   - Transform: (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
   - Band count: 1, dtype: float32
2. All 5,167,373 inside-footprint pixels must be finite (no NaN, no Inf) and in [0.0, 1.0].
3. Outside-footprint pixels (7,111,787 pixels) must be either all NaN (matching
   sample_submission.tif) or all 0.0 (all-finite variant, empirically proven on DrivenData
   via 12GEMSDOE R7 to score identically: 0.1294 == 0.1294).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import rasterio


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def validate_submission_tif(
    submission_path: Path | str,
    template_path: Path | str,
    require_outside_nan: bool | None = None,
) -> dict[str, Any]:
    """Validate a candidate submission GeoTIFF against sample_submission.tif."""
    sub_p = Path(submission_path)
    tmpl_p = Path(template_path)
    if not sub_p.exists():
        raise FileNotFoundError(f"Submission file not found: {sub_p}")
    if not tmpl_p.exists():
        raise FileNotFoundError(f"Template file not found: {tmpl_p}")

    with rasterio.open(tmpl_p) as t_src:
        t_crs = t_src.crs
        t_transform = t_src.transform
        t_shape = t_src.shape
        t_arr = t_src.read(1)
        footprint = np.isfinite(t_arr)

    with rasterio.open(sub_p) as s_src:
        s_crs = s_src.crs
        s_transform = s_src.transform
        s_shape = s_src.shape
        s_count = s_src.count
        s_dtypes = s_src.dtypes
        s_arr = s_src.read(1)

    errors: list[str] = []
    if s_crs != t_crs:
        errors.append(f"CRS mismatch: {s_crs} != {t_crs}")
    if s_shape != t_shape:
        errors.append(f"Shape mismatch: {s_shape} != {t_shape}")
    if s_transform != t_transform:
        errors.append(f"Transform mismatch: {s_transform} != {t_transform}")
    if s_count != 1:
        errors.append(f"Band count must be 1, got {s_count}")
    if s_dtypes != ("float32",):
        errors.append(f"Dtype must be ('float32',), got {s_dtypes}")

    if s_shape == t_shape:
        in_vals = s_arr[footprint]
        out_vals = s_arr[~footprint]
        n_in_nan = int(np.isnan(in_vals).sum())
        n_in_inf = int(np.isinf(in_vals).sum())
        if n_in_nan > 0:
            errors.append(
                f"Found {n_in_nan} NaN pixels inside valid footprint (causes 'Predicted values must be in range [0, 1]')"
            )
        if n_in_inf > 0:
            errors.append(f"Found {n_in_inf} Inf pixels inside valid footprint")

        finite_in = in_vals[np.isfinite(in_vals)]
        min_in = float(finite_in.min()) if finite_in.size else float("nan")
        max_in = float(finite_in.max()) if finite_in.size else float("nan")
        if finite_in.size and (min_in < 0.0 or max_in > 1.0):
            errors.append(f"In-footprint values out of [0, 1]: min={min_in}, max={max_in}")

        out_all_nan = bool(np.isnan(out_vals).all())
        out_all_zero = bool(np.isfinite(out_vals).all() and np.all(out_vals == 0.0))
        if require_outside_nan is True and not out_all_nan:
            errors.append("Outside-footprint pixels must all be NaN")
        elif require_outside_nan is False and not out_all_zero:
            errors.append("Outside-footprint pixels must all be 0.0 in all-finite mode")
        elif require_outside_nan is None and not (out_all_nan or out_all_zero):
            errors.append("Outside-footprint pixels must be either all NaN or all 0.0")
    else:
        min_in = max_in = float("nan")
        n_in_nan = n_in_inf = -1
        out_all_nan = out_all_zero = False
        in_vals = np.array([], dtype=np.float32)

    if errors:
        raise ValueError("Submission validation failed:\n  - " + "\n  - ".join(errors))

    pos_in = int((in_vals > 0.0).sum())
    return {
        "valid": True,
        "path": str(sub_p),
        "bytes": sub_p.stat().st_size,
        "sha256": sha256_file(sub_p),
        "crs": str(s_crs),
        "shape": list(s_shape),
        "transform": list(s_transform)[:6],
        "dtype": s_dtypes[0],
        "footprint_pixels": int(footprint.sum()),
        "outside_pixels": int((~footprint).sum()),
        "in_footprint_nan_count": n_in_nan,
        "in_footprint_min": min_in,
        "in_footprint_max": max_in,
        "positive_pixels": pos_in,
        "positive_fraction_of_footprint": round(pos_in / float(footprint.sum()), 6),
        "sum_mass": round(float(in_vals.sum(dtype=np.float64)), 2),
        "outside_mode": "nan" if out_all_nan else "zero_allfinite",
    }


def write_validated_submission(
    pred_2d: np.ndarray,
    template_path: Path | str,
    out_path: Path | str,
    outside_nan: bool = True,
) -> dict[str, Any]:
    """Sanitize, write, and strictly re-read/validate a single-band float32 GeoTIFF."""
    tmpl_p = Path(template_path)
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(tmpl_p) as t_src:
        profile = t_src.profile.copy()
        footprint = np.isfinite(t_src.read(1))

    arr = np.nan_to_num(pred_2d, nan=0.0, posinf=1.0, neginf=0.0).astype(np.float32)
    arr = np.clip(arr, 0.0, 1.0)
    if outside_nan:
        arr = np.where(footprint, arr, np.float32(np.nan))
        nodata_val = np.nan
    else:
        arr = np.where(footprint, arr, np.float32(0.0))
        nodata_val = None

    profile.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        compress="deflate",
        predictor=3,
        nodata=nodata_val,
    )
    with rasterio.open(out_p, "w", **profile) as dst:
        dst.write(arr, 1)

    return validate_submission_tif(out_p, tmpl_p, require_outside_nan=outside_nan)
