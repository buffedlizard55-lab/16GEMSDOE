"""Build experimental H16-derived GeoTIFF artifacts and record format/spatial checks.

The NaN-outside TIFF follows the documented outside-bounds convention. The all-finite
and pure-physical files are diagnostic zero-outside variants, not format-compliant
submission files. The NaN and all-finite primary rasters are the same prediction within
the evaluation footprint. No live score is inferred by this script; local spatial
profiles are descriptive and do not establish geological correctness.
"""
from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt, gaussian_filter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.metric import ridge_nms, verify_organizer_worked_example
from gems.validator import sha256_file, validate_submission_tif, write_validated_submission

DATA_DIR = ROOT / "data"
EVIDENCE_DIR = ROOT / "evidence"
DOWNLOADS_DIR = ROOT / "docs" / "downloads"


def compute_spatial_profile(
    pred_bin: np.ndarray,
    footprint: np.ndarray,
    labels: np.ndarray,
    dist_cat: np.ndarray,
    ens12_off: np.ndarray,
    g7_off: np.ndarray,
) -> dict:
    off = pred_bin & footprint & (~labels)
    on = pred_bin & footprint & labels
    n_off = int(off.sum())
    d_le3 = int((off & (dist_cat <= 3.0)).sum())
    d_4_15 = int((off & (dist_cat > 3.0) & (dist_cat <= 15.0)).sum())
    d_gt15 = int((off & (dist_cat > 15.0)).sum())

    if n_off > 0:
        edt_off = distance_transform_edt(~off)
        w_off = np.maximum(1.0 - edt_off / 3.0, 0.0) * (footprint & (~labels))
        reach_px = int(((w_off > 0) & footprint & (~labels)).sum())
        integral_w = float(w_off.sum())
    else:
        reach_px = 0
        integral_w = 0.0

    off_fp_total = int((footprint & (~labels)).sum())
    reach_frac = reach_px / max(1, off_fp_total)
    mean_w = integral_w / max(1, off_fp_total)
    raw_frac = n_off / max(1, off_fp_total)
    lift = mean_w / max(1e-9, raw_frac)

    # Overlap with ens12 (0.1563) and 7GEMSDOE (0.1461)
    inter_ens12 = int((off & ens12_off).sum())
    inter_g7 = int((off & g7_off).sum())
    edt_ens12 = distance_transform_edt(~ens12_off)
    novel_beyond_300m_ens12 = int((off & (edt_ens12 > 3.0)).sum())

    return {
        "on_catalogue_px": int(on.sum()),
        "off_catalogue_px": n_off,
        "off_d_le_3_px": d_le3,
        "off_d_4_15_px": d_4_15,
        "off_d_gt_15_px": d_gt15,
        "far_field_frac_gt_3": round((d_4_15 + d_gt15) / max(1, n_off), 4),
        "deep_basin_frac_gt_15": round(d_gt15 / max(1, n_off), 4),
        "reach_300m_off_cat_px": reach_px,
        "reach_300m_off_cat_frac": round(reach_frac, 4),
        "mean_300m_kernel_weight": round(mean_w, 4),
        "kernel_support_per_emitted_pixel_ratio": round(lift, 3),
        "overlap_ens12_px": inter_ens12,
        "overlap_7gemsdoe_px": inter_g7,
        "novel_beyond_300m_of_ens12_px": novel_beyond_300m_ens12,
    }


def main() -> None:
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    with rasterio.open(DATA_DIR / "sample_submission.tif") as src:
        footprint = np.isfinite(src.read(1))
    with rasterio.open(DATA_DIR / "labels.tif") as src:
        labels = (src.read(1) > 0) & footprint

    fp_idx = np.flatnonzero(footprint.ravel())
    dist_cat = distance_transform_edt(~labels).astype(np.float32)

    # Load cached footprint features & 4-quadrant OOF H16-1 probabilities
    feats = np.load(DATA_DIR / "cache" / "features_fp.npz")
    oofs = np.load(DATA_DIR / "cache" / "oof_probs_h16_1.npz")
    p_h16_1_fp = oofs["h16_1"]
    p_scarp_pure_fp = oofs["h16_3_pure"]
    p_h16_3_fp = oofs["h16_3"]
    p_h16_2_fp = oofs["h16_2"]
    p_h16_4_fp = oofs["h16_4"]
    lid_ok_fp = feats["lid1m_valid"] > 0.5

    # Reconstruct 2D surfaces on the 3730 x 3292 grid
    p_h16_1_2d = np.zeros(footprint.shape, dtype=np.float32)
    p_h16_1_2d.ravel()[fp_idx] = p_h16_1_fp

    lid_ok_2d = np.zeros(footprint.shape, dtype=bool)
    lid_ok_2d.ravel()[fp_idx] = lid_ok_fp

    # Load 4-fold OOF spatial context detector probability (ctx_oof_topo_rad) and ens12 + 7GEMSDOE
    ctx_2d = np.zeros(footprint.shape, dtype=np.float32)
    ctx_2d.ravel()[fp_idx] = 0.50 * feats["ctx_oof_topo_rad"] + 0.30 * feats["ctx_oof_topo"] + 0.20 * feats["ctx_oof_base"]

    with rasterio.open(DATA_DIR / "derived" / "ens12_7f00890a.tif") as src:
        ens12_2d = (np.nan_to_num(src.read(1), nan=0.0) > 0.5) & footprint
    with rasterio.open("/tmp/audit/7GEMSDOE/downloads/gems7-lidarscarp-ridge-top2pct-36c3a3f341c8.tif") as src:
        g7_2d = (np.nan_to_num(src.read(1), nan=0.0) > 0.5) & footprint

    ens12_off = ens12_2d & (~labels)
    g7_off = g7_2d & (~labels)

    # Experimental composite mask, built from OOF model surfaces and historical
    # prediction masks. This is a reproducible artifact, not a live-score or
    # submission recommendation; it has not itself passed the spatial holdout gate.
    # The local catalogue mask is applied explicitly as a design choice. The
    # historical 8GEMSDOE comparison does not establish how the evaluator treats
    # catalogue pixels.


    # Extract 1-px Hessian directional ridges of our H16-1 calibrated multi-scale surface
    h16_1_ridge = ridge_nms(p_h16_1_2d, footprint, sigma=1.0)
    # Also extract 1-px Hessian directional ridges of the combined H16-1 + OOF spatial context field
    joint_surface = np.where(
        lid_ok_2d,
        0.55 * p_h16_1_2d + 0.45 * ctx_2d,
        0.60 * p_h16_1_2d + 0.40 * ctx_2d,
    ).astype(np.float32)
    joint_ridge = ridge_nms(joint_surface, footprint, sigma=1.0)

    off_mask = footprint & (~labels)

    def select_top_k_mask(pool_mask: np.ndarray, score_arr: np.ndarray, k: int) -> np.ndarray:
        idx = np.flatnonzero(pool_mask.ravel())
        k_use = min(k, len(idx))
        vals = score_arr.ravel()[idx]
        sel = idx[np.argpartition(vals, -k_use)[-k_use:]]
        out = np.zeros(pool_mask.shape, dtype=bool)
        out.ravel()[sel] = True
        return out

    # Component A: retain up to 148,000 ens12 off-catalogue pixels ranked by
    # the composite OOF/context score below. This is a fixed design choice; no
    # true-positive or score benefit is inferred from the ranking.
    ens12_joint_score = 0.55 * p_h16_1_2d + 0.45 * ctx_2d + 0.30 * g7_off.astype(np.float32) + 0.05 * np.minimum(dist_cat, 10.0)
    ens12_keep = select_top_k_mask(ens12_off, ens12_joint_score, 148000)

    # Distance from retained ens12 core (so we only add novel ridges outside ens12's immediate trace!)
    edt_ens12_keep = distance_transform_edt(~ens12_keep)

    # Component B: select up to 24,000 7GEMSDOE pixels outside the retained
    # ens12 mask, ranked by the H16-1/context score. This thresholding is a
    # hypothesis choice, not a measured marginal-TP comparison.
    g7_cand = g7_off & (~ens12_keep) & (edt_ens12_keep >= 2.0) & (dist_cat > 2.0)
    g7_rank_score = p_h16_1_2d + 0.35 * ctx_2d
    g7_novel = select_top_k_mask(g7_cand, g7_rank_score, 24000)

    # Component C: add H16-1/joint-surface ridges in lidar-gap cells, then add
    # corroborated ridges within the lidar-covered area. Selection sizes below
    # are fixed design parameters, not validated performance estimates.
    # (c1) 18,500 candidate ridges in the local 1m-lidar data gap:
    cand_gap_pool = (
        off_mask & (~lid_ok_2d) & (~ens12_keep) & (edt_ens12_keep >= 2.0) & (h16_1_ridge | joint_ridge) & (dist_cat > 2.5)
    )
    h16_gap_ridges = select_top_k_mask(cand_gap_pool, joint_surface, 18500)

    # (c2) In lidar-covered cells, select up to 7,500 intersecting H16-1 and joint ridges:
    edt_so_far = distance_transform_edt(~(ens12_keep | g7_novel))
    cand_lid_pool = (
        off_mask & lid_ok_2d & (~ens12_keep) & (~g7_novel) & (edt_so_far >= 2.5) & (h16_1_ridge & joint_ridge) & (dist_cat > 3.0)
    )
    h16_lid_ridges = select_top_k_mask(cand_lid_pool, joint_surface, 7500)

    primary_bin = (ens12_keep | g7_novel | h16_gap_ridges | h16_lid_ridges) & off_mask
    primary_f32 = primary_bin.astype(np.float32)

    # Experimental physical-feature alternative. It uses the local catalogue mask,
    # lidar scarp mask, and H16-1 OOF surface; it is therefore neither fully
    # independent of prior submissions nor validated by the H16-1 holdout score.
    # The pixel budgets below define a distinct candidate recipe only.
    pure_lid_pool = off_mask & lid_ok_2d & (g7_off | h16_1_ridge) & (dist_cat > 1.5)
    pure_lid_score = p_h16_1_2d + 0.30 * g7_off.astype(np.float32)
    k_lid = 82000
    lid_idx = np.flatnonzero(pure_lid_pool.ravel())
    top_lid_idx = lid_idx[np.argpartition(pure_lid_score.ravel()[lid_idx], -k_lid)[-k_lid:]]

    pure_gap_pool = off_mask & (~lid_ok_2d) & h16_1_ridge & (dist_cat > 2.0)
    k_gap = 26500
    gap_idx = np.flatnonzero(pure_gap_pool.ravel())
    top_gap_idx = gap_idx[np.argpartition(p_h16_1_2d.ravel()[gap_idx], -k_gap)[-k_gap:]]

    pure_phys_bin = np.zeros(footprint.shape, dtype=bool)
    pure_phys_bin.ravel()[top_lid_idx] = True
    pure_phys_bin.ravel()[top_gap_idx] = True
    pure_phys_f32 = pure_phys_bin.astype(np.float32)

    # Write validated GeoTIFF files
    p1_allfinite_path = (
        DOWNLOADS_DIR / "gems16-h16-1-seamfree-multiscale-ridge-allfinite-20260929-a16f01.tif"
    )
    p1_nanmask_path = (
        DOWNLOADS_DIR / "gems16-h16-1-seamfree-multiscale-ridge-nanmask-20260929-b16f02.tif"
    )
    p2_pure_path = (
        DOWNLOADS_DIR / "gems16-h16-1-pure-physical-scarp-worm-allfinite-20260929-c16f03.tif"
    )

    rep_p1_allfinite = write_validated_submission(
        primary_f32, DATA_DIR / "sample_submission.tif", p1_allfinite_path, outside_nan=False
    )
    rep_p1_nanmask = write_validated_submission(
        primary_f32, DATA_DIR / "sample_submission.tif", p1_nanmask_path, outside_nan=True
    )
    rep_p2_pure = write_validated_submission(
        pure_phys_f32, DATA_DIR / "sample_submission.tif", p2_pure_path, outside_nan=False
    )

    # Package only the outside-NaN variant, which follows the documented
    # outside-bounds convention. The all-finite zero-outside file is diagnostic.
    p1_zip_path = DOWNLOADS_DIR / "gems16-h16-1-seamfree-multiscale-ridge-nanmask-20260929-b16f02.zip"
    with zipfile.ZipFile(p1_zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(p1_nanmask_path, arcname=p1_nanmask_path.name)

    # Profile both candidates and verify 100% uniqueness against all 19 historical group submissions
    prof_primary = compute_spatial_profile(primary_bin, footprint, labels, dist_cat, ens12_off, g7_off)
    prof_pure = compute_spatial_profile(pure_phys_bin, footprint, labels, dist_cat, ens12_off, g7_off)

    # Check lidar-gap coverage specifically!
    gap_mask = off_mask & (~lid_ok_2d)
    prof_primary["emitted_in_24pct_lidar_gap_px"] = int((primary_bin & gap_mask).sum())
    prof_primary["ens12_pruned_px"] = int(ens12_keep.sum())
    prof_primary["g7_novel_scarp_px"] = int(g7_novel.sum())
    prof_primary["h16_1_gapfill_px"] = int(h16_gap_ridges.sum())
    prof_primary["h16_1_lidar_novel_px"] = int(h16_lid_ridges.sum())
    prof_pure["emitted_in_24pct_lidar_gap_px"] = int((pure_phys_bin & gap_mask).sum())

    # Check exact bytes against the recorded historic submissions. Equal pixel
    # counts are not evidence of distinct predictions, so do not treat them as a
    # uniqueness test. The all-finite and NaN-outside primary files intentionally
    # share the same in-footprint prediction and are not separate experiments.
    forensic = json.loads((EVIDENCE_DIR / "group_forensic_audit.json").read_text())
    prior_shas = {r["sha256"]: r["repo"] for r in forensic["submissions"]}

    generated_shas = [rep_p1_allfinite["sha256"], rep_p1_nanmask["sha256"], rep_p2_pure["sha256"]]
    uniqueness_checks = {
        "generated_artifact_sha256s_pairwise_unique": len(set(generated_shas)) == len(generated_shas),
        "primary_allfinite_sha256_unique_vs_history": rep_p1_allfinite["sha256"] not in prior_shas,
        "primary_nanmask_sha256_unique_vs_history": rep_p1_nanmask["sha256"] not in prior_shas,
        "pure_physical_sha256_unique_vs_history": rep_p2_pure["sha256"] not in prior_shas,
        "primary_variants_share_prediction_array": True,
        "primary_vs_pure_physical_hamming_distance_px": int(np.logical_xor(primary_bin, pure_phys_bin).sum()),
        "primary_vs_ens12_hamming_distance_px": int(np.logical_xor(primary_bin, ens12_off).sum()),
        "primary_vs_7gemsdoe_hamming_distance_px": int(np.logical_xor(primary_bin, g7_off).sum()),
    }
    assert all(
        uniqueness_checks[key]
        for key in (
            "generated_artifact_sha256s_pairwise_unique",
            "primary_allfinite_sha256_unique_vs_history",
            "primary_nanmask_sha256_unique_vs_history",
            "pure_physical_sha256_unique_vs_history",
        )
    ), "A generated artifact duplicates a recorded historical file by SHA-256."

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "submission_recommendation": "No artifact is recommended for a live submission until the exact candidate passes the spatially blocked holdout gate. H17-1 failed; current artifacts are for reproducible review only.",
        "interpretation_limits": [
            "Spatial profiles and catalogue-distance bands describe predictions; they are not true-positive estimates and do not predict leaderboard DTI.",
            "All-finite zero-outside variants are diagnostic and do not follow the required outside-bounds null convention.",
            "The primary NaN-outside and all-finite files share the same in-footprint prediction and are not distinct experiments."
        ],
        "organizer_metric_worked_example": verify_organizer_worked_example(),
        "uniqueness_audit": uniqueness_checks,
        "candidates": {
            "primary_allfinite": {
                "filename": p1_allfinite_path.name,
                "drivendata_submission_note": (
                    "16GEMSDOE | H16-1 Seam-Free Multi-Scale Tectonic Ridge Synthesis "
                    "(1m 3DEP Lidar Antislope/Piedmont Scarp + 10m 3DEP DEM Asymmetry Gap-Fill + "
                    "1.5km Strike Geopotential Worms + Hydrothermal Conduits + OOF Spatial Context "
                    "| 1px Hessian ridge_nms | All-Finite [0,1] float32 | ID: a16f01)"
                ),
                "validation": rep_p1_allfinite,
                "spatial_profile": prof_primary,
            },
            "primary_nanmask": {
                "filename": p1_nanmask_path.name,
                "zip_filename": p1_zip_path.name,
                "zip_size_bytes": p1_zip_path.stat().st_size,
                "zip_sha256": sha256_file(p1_zip_path),
                "drivendata_submission_note": (
                    "16GEMSDOE | H16-1 Seam-Free Multi-Scale Tectonic Ridge Synthesis "
                    "(Footprint-Valid [0,1], Outside-NaN Twin | 1px Hessian ridge_nms | ID: b16f02)"
                ),
                "validation": rep_p1_nanmask,
                "spatial_profile": prof_primary,
            },
            "pure_physical_contender": {
                "filename": p2_pure_path.name,
                "drivendata_submission_note": (
                    "16GEMSDOE | H16-1 Pure Physical Multi-Scale Scarp-Worm-Hydrothermal Ridge "
                    "(Experimental physical-only variant; 1m Lidar + 10m DEM + Strike Worms + "
                    "Hydrothermal | Diagnostic all-finite [0,1] float32 | ID: c16f03)"
                ),
                "validation": rep_p2_pure,
                "spatial_profile": prof_pure,
            },
        },
    }

    out_path = EVIDENCE_DIR / "submission_validation_report.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Wrote {out_path}")
    print(
        f"Primary (a16f01; diagnostic all-finite variant): off_cat={prof_primary['off_catalogue_px']:,} px, "
        f"Reach300m={prof_primary['reach_300m_off_cat_frac']*100:.2f}%, "
        f"Kernel-support ratio={prof_primary['kernel_support_per_emitted_pixel_ratio']:.2f}, "
        f"GapFill={prof_primary['emitted_in_24pct_lidar_gap_px']:,} px. No DTI is projected."
    )
    print(
        f"Pure physical diagnostic (c16f03): off_cat={prof_pure['off_catalogue_px']:,} px, "
        f"Reach300m={prof_pure['reach_300m_off_cat_frac']*100:.2f}%. No DTI is projected."
    )


if __name__ == "__main__":
    main()
