"""Spatially validate H17-1 cross-sensor potential-field edge agreement.

This is a validation-only experiment. It never writes a submission GeoTIFF and does
not contact DrivenData. It compares the candidate against the existing baseline and
H16-1 OOF predictions using the same four-quadrant holdout protocol.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, gaussian_filter, uniform_filter
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.metric import dti_score_fast, ridge_nms

DATA = ROOT / "data"
EVIDENCE = ROOT / "evidence"
SEED = 20260929


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _folds(footprint: np.ndarray) -> tuple[np.ndarray, list[str]]:
    yy, xx = np.nonzero(footprint)
    ym, xm = int(np.median(yy)), int(np.median(xx))
    gy, gx = np.ogrid[: footprint.shape[0], : footprint.shape[1]]
    out = np.full(footprint.shape, -1, np.int8)
    out[(gy < ym) & (gx < xm) & footprint] = 0
    out[(gy < ym) & (gx >= xm) & footprint] = 1
    out[(gy >= ym) & (gx < xm) & footprint] = 2
    out[(gy >= ym) & (gx >= xm) & footprint] = 3
    return out, ["NW", "NE", "SW", "SE"]


def _thin_components(truth: np.ndarray, keep_frac: float, seed: int) -> np.ndarray:
    from scipy.ndimage import label

    components, n = label(truth, structure=np.ones((3, 3), dtype=np.uint8))
    if n == 0:
        return np.zeros_like(truth, dtype=bool)
    rng = np.random.default_rng(seed)
    keep = rng.choice(np.arange(1, n + 1), size=max(1, int(round(keep_frac * n))), replace=False)
    return np.isin(components, keep)


def _fill_nans(arr: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Interpolate only the few internal input NaNs with a normalized local mean."""
    # The source rasters also use large finite sentinels for missing data; treat those
    # as invalid just like NaN rather than allowing them to overflow derivatives.
    good = np.isfinite(arr) & (arr > -1e20) & (arr < 1e20) & footprint
    safe = np.where(good, arr, 0.0).astype(np.float32)
    num = gaussian_filter(safe, sigma=2.0)
    den = gaussian_filter(good.astype(np.float32), sigma=2.0)
    interpolated = num / np.maximum(den, 1e-6)
    out = np.where(good, safe, interpolated)
    out[~footprint] = 0.0
    return out.astype(np.float32)


def _potential_edge_features(footprint: np.ndarray) -> dict[str, np.ndarray]:
    """Generate multiscale magnetic/gravity edge agreement features.

    For sigma 1 and 3 pixels, calculate gradient vectors of RTP magnetic anomaly and
    isostatic gravity anomaly. Normalize gradient magnitudes using robust full-region
    percentiles (no labels), then emit parallel-normal agreement and cross-field
    orientation-interaction features. The latter is an exploratory lineament-junction
    proxy, not a direct fault observation.
    """
    with rasterio.open(DATA / "training_features.tif") as src:
        # Raster band numbering matches verified raster descriptions in data_verification.json.
        rtp = _fill_nans(src.read(2).astype(np.float32), footprint)
        gravity = _fill_nans(src.read(13).astype(np.float32), footprint)

    result: dict[str, np.ndarray] = {}
    for sigma in (1.0, 3.0):
        mr = gaussian_filter(rtp, sigma=sigma)
        gr = gaussian_filter(gravity, sigma=sigma)
        my, mx = np.gradient(mr)
        gy, gx = np.gradient(gr)
        mm = np.hypot(mx, my)
        gm = np.hypot(gx, gy)
        mscale = max(float(np.quantile(mm[footprint], 0.99)), 1e-8)
        gscale = max(float(np.quantile(gm[footprint], 0.99)), 1e-8)
        mn = np.clip(mm / mscale, 0.0, 4.0)
        gn = np.clip(gm / gscale, 0.0, 4.0)
        # Form unit gradient vectors first to avoid overflow in products of large
        # physical-unit derivatives. Clamp tiny/flat gradients to zero magnitude.
        valid_pair = (mm > 1e-12) & (gm > 1e-12)
        umx = mx / np.maximum(mm, 1e-12)
        umy = my / np.maximum(mm, 1e-12)
        ugx = gx / np.maximum(gm, 1e-12)
        ugy = gy / np.maximum(gm, 1e-12)
        dot = np.where(valid_pair, np.abs(umx * ugx + umy * ugy), 0.0)
        cross = np.where(valid_pair, np.abs(umx * ugy - umy * ugx), 0.0)
        dot = np.clip(dot, 0.0, 1.0)
        cross = np.clip(cross, 0.0, 1.0)
        edge_strength = np.sqrt(mn * gn)
        suffix = f"s{int(sigma)}"
        result[f"mag_gradient_{suffix}"] = np.where(footprint, mn, 0.0).astype(np.float32)
        result[f"gravity_gradient_{suffix}"] = np.where(footprint, gn, 0.0).astype(np.float32)
        result[f"parallel_edge_agreement_{suffix}"] = np.where(
            footprint, edge_strength * dot, 0.0
        ).astype(np.float32)
        result[f"cross_edge_interaction_{suffix}"] = np.where(
            footprint, edge_strength * cross, 0.0
        ).astype(np.float32)
        del mr, gr, my, mx, gy, gx, mm, gm, mn, gn, dot, cross, edge_strength

    return result


def _score_oof(
    probs_fp: np.ndarray,
    fp_idx: np.ndarray,
    footprint: np.ndarray,
    labels: np.ndarray,
    fold_2d: np.ndarray,
    fold_names: list[str],
    budget_frac: float = 0.025,
) -> dict:
    score_2d = np.zeros(footprint.shape, dtype=np.float32)
    score_2d.ravel()[fp_idx] = probs_fp
    ridge = ridge_nms(score_2d, footprint, sigma=1.0)
    ranked = np.where(ridge, score_2d + 1.0, score_2d * 0.5)
    details: dict[str, dict[str, float | int]] = {}
    dense_scores, sparse_scores = [], []

    for fold_id, name in enumerate(fold_names):
        fold_mask = (fold_2d == fold_id) & footprint
        rows, cols = np.nonzero(fold_mask)
        if len(rows) == 0:
            raise ValueError(f"Empty holdout fold: {name}")
        sl = (slice(int(rows.min()), int(rows.max()) + 1), slice(int(cols.min()), int(cols.max()) + 1))
        dense_truth = labels[sl] & fold_mask[sl]
        sparse_truth = _thin_components(dense_truth, keep_frac=0.20, seed=4242 + fold_id)
        neutral_catalogue = dense_truth & (~sparse_truth)
        k_emit = max(1, int(round(budget_frac * int(fold_mask.sum()))))
        fold_idx = np.flatnonzero(fold_mask.ravel())
        vals = ranked.ravel()[fold_idx]
        chosen = fold_idx[np.argpartition(vals, -k_emit)[-k_emit:]]
        pred = np.zeros(footprint.shape, dtype=bool)
        pred.ravel()[chosen] = True

        dense = dti_score_fast(pred[sl], dense_truth, valid_mask=fold_mask[sl])
        sparse = dti_score_fast(
            pred[sl], sparse_truth, valid_mask=fold_mask[sl], catalogue_mask=neutral_catalogue
        )
        dense_scores.append(float(dense["dti"]))
        sparse_scores.append(float(sparse["dti"]))
        details[name] = {
            "dense_dti": round(float(dense["dti"]), 5),
            "sparse_dti": round(float(sparse["dti"]), 5),
            "dense_coverage": round(float(dense["coverage"]), 5),
            "sparse_coverage": round(float(sparse["coverage"]), 5),
            "emitted_px": int(pred[sl].sum()),
        }

    return {
        "folds": details,
        "mean_dense_dti": round(float(np.mean(dense_scores)), 5),
        "mean_sparse_dti": round(float(np.mean(sparse_scores)), 5),
    }


def main() -> None:
    required = [DATA / "training_features.tif", DATA / "labels.tif", DATA / "sample_submission.tif"]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit("Missing prepared data; run scripts/download_competition_data.sh and scripts/prepare_data.py: " + ", ".join(missing))

    with rasterio.open(DATA / "sample_submission.tif") as src:
        template = src.read(1)
        footprint = np.isfinite(template)
    with rasterio.open(DATA / "labels.tif") as src:
        labels = (src.read(1) > 0) & footprint

    cache = DATA / "cache" / "features_fp.npz"
    oof_cache = DATA / "cache" / "oof_probs_all_arms.npz"
    h16_cache = DATA / "cache" / "oof_probs_h16_1.npz"
    for p in (cache, oof_cache, h16_cache):
        if not p.exists():
            raise SystemExit(f"Missing reproducible holdout cache {p}; run scripts/run_spatial_holdout_and_build.py first.")

    feats_file = np.load(cache)
    fp_idx = np.flatnonzero(footprint.ravel())
    fold_2d, fold_names = _folds(footprint)
    fold_fp = fold_2d.ravel()[fp_idx]
    y_fp = labels.ravel()[fp_idx]
    near_cat_fp = binary_dilation(labels, iterations=3).ravel()[fp_idx]

    base_cols = [
        "tmi_hg", "tmi_vg", "tc", "grav_slope", "grav_vg", "grav_hg_abs",
        "elev_slope", "elev_slope_anom15", "det_elev_local15", "rtp_local15",
        "grav_local15", "cond_local15", "depth_base_grad",
    ]
    h17 = _potential_edge_features(footprint)
    h17_cols = list(h17)
    for name, arr in h17.items():
        h17[name] = arr.ravel()[fp_idx]

    oof_candidate = np.zeros(len(fp_idx), dtype=np.float32)
    rng = np.random.default_rng(SEED)
    for fold_id, fold_name in enumerate(fold_names):
        test_2d = (fold_2d == fold_id) & footprint
        buffer = binary_dilation(test_2d, iterations=15)
        train_mask = (fold_fp != fold_id) & (~buffer.ravel()[fp_idx])
        test_mask = fold_fp == fold_id
        pos_idx = np.flatnonzero(train_mask & y_fp)
        neg_idx = np.flatnonzero(train_mask & (~near_cat_fp))
        if min(len(pos_idx), len(neg_idx)) == 0:
            raise ValueError(f"No training positives/negatives for fold {fold_name}")
        pos = rng.choice(pos_idx, size=min(40000, len(pos_idx)), replace=False)
        neg = rng.choice(neg_idx, size=min(120000, len(neg_idx)), replace=False)
        train_idx = np.concatenate([pos, neg])
        y_train = np.r_[np.ones(len(pos), dtype=np.int8), np.zeros(len(neg), dtype=np.int8)]
        weight = np.where(y_train == 1, 0.5 / len(pos), 0.5 / len(neg)) * len(train_idx)
        cols = base_cols + h17_cols
        x_train = np.column_stack([feats_file[c][train_idx] for c in base_cols] + [h17[c][train_idx] for c in h17_cols])
        clf = HistGradientBoostingClassifier(
            max_iter=150,
            max_leaf_nodes=31,
            min_samples_leaf=80,
            learning_rate=0.06,
            l2_regularization=2.0,
            early_stopping=False,
            random_state=SEED + fold_id,
        )
        clf.fit(x_train, y_train, sample_weight=weight)
        test_idx = np.flatnonzero(test_mask)
        x_test = np.column_stack([feats_file[c][test_idx] for c in base_cols] + [h17[c][test_idx] for c in h17_cols])
        oof_candidate[test_idx] = clf.predict_proba(x_test)[:, 1].astype(np.float32)
        print(f"Trained H17-1 held-out fold {fold_id} ({fold_name}); train={len(train_idx):,}, test={len(test_idx):,}")
        del clf, x_train, x_test

    prior_oof = np.load(oof_cache)
    h16_oof = np.load(h16_cache)
    reference_scores = {
        "baseline": _score_oof(prior_oof["Baseline_Bands19_DeReg"], fp_idx, footprint, labels, fold_2d, fold_names),
        "H16-1_current_holdout_best": _score_oof(h16_oof["h16_1"], fp_idx, footprint, labels, fold_2d, fold_names),
    }
    candidate_score = _score_oof(oof_candidate, fp_idx, footprint, labels, fold_2d, fold_names)

    h16_sparse = [reference_scores["H16-1_current_holdout_best"]["folds"][n]["sparse_dti"] for n in fold_names]
    h16_dense = [reference_scores["H16-1_current_holdout_best"]["folds"][n]["dense_dti"] for n in fold_names]
    c_sparse = [candidate_score["folds"][n]["sparse_dti"] for n in fold_names]
    c_dense = [candidate_score["folds"][n]["dense_dti"] for n in fold_names]
    sparse_wins = sum(c > h for c, h in zip(c_sparse, h16_sparse))
    dense_wins = sum(c > h for c, h in zip(c_dense, h16_dense))
    no_bad_fold = all(c - h >= -0.01 for c, h in zip(c_sparse + c_dense, h16_sparse + h16_dense))
    pass_gate = bool(
        candidate_score["mean_sparse_dti"] > reference_scores["H16-1_current_holdout_best"]["mean_sparse_dti"]
        and candidate_score["mean_dense_dti"] > reference_scores["H16-1_current_holdout_best"]["mean_dense_dti"]
        and sparse_wins >= 3
        and no_bad_fold
    )

    data_verification = json.loads((EVIDENCE / "data_verification.json").read_text())
    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_id": "H17-1",
        "candidate_name": "Cross-sensor potential-field edge agreement",
        "status": "PASS_HOLDOUT_GATE" if pass_gate else "FAIL_HOLDOUT_GATE",
        "submission_slot_spent": False,
        "submission_geotiff_created": False,
        "gate": {
            "mean_dense_and_sparse_must_exceed_H16_1": True,
            "sparse_folds_must_win_at_least": 3,
            "maximum_per_fold_dti_loss": 0.01,
            "candidate_sparse_fold_wins": sparse_wins,
            "candidate_dense_fold_wins": dense_wins,
            "all_dense_and_sparse_folds_within_0_01": no_bad_fold,
            "passed": pass_gate,
        },
        "method": {
            "folds": fold_names,
            "partition": "four contiguous geographic quadrants from footprint row/column medians",
            "spatial_buffer_pixels": 15,
            "training_sampling": "up to 40,000 mapped positive pixels + 120,000 negatives outside 3-pixel catalogue collar per fold",
            "classifier": "HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=31,min_samples_leaf=80,learning_rate=0.06,l2_regularization=2.0)",
            "prediction_budget_per_fold": 0.025,
            "ranking": "same 1-pixel ridge_nms boost and top-budget selection used by prior holdout",
            "sparse_proxy": "deterministic random 20% of connected held-out catalogue components; remaining held-out components neutral in sparse false-positive calculation",
            "candidate_features": h17_cols,
            "candidate_feature_definition": "RTP magnetic and isostatic-gravity gradient magnitude at Gaussian sigma 1 and 3 pixels; robust 99th-percentile normalization; parallel-normal agreement and cross-sensor orientation interaction",
            "random_seed": SEED,
            "scoring": "repository dti_score_fast; this is a known-catalogue spatial-transfer proxy, not hidden leaderboard evaluation",
        },
        "input_files": {
            "training_features_tif_sha256": _sha256(DATA / "training_features.tif"),
            "labels_tif_sha256": _sha256(DATA / "labels.tif"),
            "sample_submission_tif_sha256": _sha256(DATA / "sample_submission.tif"),
            "training_features_recorded_sha256": data_verification["rasters"]["training_features.tif"]["sha256"],
            "feature_oof_cache_sha256": _sha256(oof_cache),
            "H16_1_oof_cache_sha256": _sha256(h16_cache),
        },
        "results": {
            "baseline": reference_scores["baseline"],
            "H16_1_current_holdout_best": reference_scores["H16-1_current_holdout_best"],
            "H17_1_candidate": candidate_score,
        },
        "interpretation": (
            "A holdout pass only warrants a separately reviewed experiment; it does not show the prediction is a fault, "
            "prove improvement on hidden labels, or guarantee an improved competition score."
        ),
    }
    output = EVIDENCE / "hypothesis_h17_1_validation.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "gate": result["gate"], "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
