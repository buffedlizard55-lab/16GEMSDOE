"""End-to-end unit and integration tests for the 16GEMSDOE pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems.metric import (
    dti_score_fast,
    marginal_inclusion_threshold,
    ridge_nms,
    verify_organizer_worked_example,
)
from gems.validator import validate_submission_tif, write_validated_submission


def test_organizer_worked_example_exact():
    res = verify_organizer_worked_example()
    assert res["matches_0_60"] is True
    assert abs(res["TP_w"] - 3.0) < 1e-6
    assert abs(res["FP_w"] - 1.89) < 1e-2
    assert abs(res["FN_w"] - 2.0) < 1e-6
    assert abs(res["DTI_rounded_2dec"] - 0.60) < 1e-6


def test_catalogue_mask_neutrality():
    """Unit-test the metric's optional neutral mask; this does not prove leaderboard behavior."""
    H, W = 64, 64
    valid = np.ones((H, W), dtype=bool)
    cat = np.zeros((H, W), dtype=bool)
    cat[10, 10:50] = True
    new_fault = np.zeros((H, W), dtype=bool)
    new_fault[40, 10:50] = True

    pred_off_only = np.zeros((H, W), dtype=bool)
    pred_off_only[41, 15:45] = True
    pred_with_cat = pred_off_only | cat

    r1 = dti_score_fast(pred_off_only, new_fault, valid_mask=valid, catalogue_mask=cat)
    r2 = dti_score_fast(pred_with_cat, new_fault, valid_mask=valid, catalogue_mask=cat)
    assert abs(r1["dti"] - r2["dti"]) < 1e-9


def test_marginal_inclusion_threshold():
    tau = marginal_inclusion_threshold(current_dti=0.1563, alpha=0.2)
    assert 0.032 < tau < 0.033


def test_ridge_nms_preserves_continuous_line():
    H, W = 50, 50
    valid = np.ones((H, W), dtype=bool)
    yy, xx = np.ogrid[:H, :W]
    # Gaussian ridge along row y=25
    score = np.exp(-((yy - 25.0) ** 2) / (2.0 * 1.5**2)).astype(np.float32)
    r = ridge_nms(score, valid, sigma=1.0)
    # Centerline row 25 should be preserved across interior columns
    assert r[25, 5:45].sum() >= 38
    # Flanking rows should be suppressed
    assert r[23, 5:45].sum() == 0
    assert r[27, 5:45].sum() == 0


def test_validator_rejects_in_footprint_nan_and_out_of_range(tmp_path: Path):
    tmpl = ROOT / "data" / "sample_submission.tif"
    with rasterio.open(tmpl) as src:
        profile = src.profile.copy()
        fp = np.isfinite(src.read(1))

    # Create a corrupt raster with 5 NaNs inside the valid footprint (simulating raw feature NaNs)
    bad_arr = np.zeros(fp.shape, dtype=np.float32)
    fp_idx = np.flatnonzero(fp.ravel())
    bad_arr.ravel()[fp_idx[:5]] = np.nan
    bad_tif = tmp_path / "bad_in_fp_nan.tif"
    with rasterio.open(bad_tif, "w", **profile) as dst:
        dst.write(bad_arr, 1)

    with pytest.raises(ValueError, match="NaN pixels"):
        validate_submission_tif(bad_tif, tmpl, require_outside_nan=False)

    # Create a corrupt raster with value > 1.0
    bad_range = np.zeros(fp.shape, dtype=np.float32)
    bad_range.ravel()[fp_idx[0]] = 1.05
    bad_range_tif = tmp_path / "bad_range.tif"
    with rasterio.open(bad_range_tif, "w", **profile) as dst:
        dst.write(bad_range, 1)

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        validate_submission_tif(bad_range_tif, tmpl, require_outside_nan=False)

    # The official format requires null/NaN outside bounds, even if the in-footprint
    # predictions are numerically valid. Zero-outside remains inspectable only as a diagnostic.
    zero_outside = tmp_path / "zero_outside.tif"
    with rasterio.open(zero_outside, "w", **profile) as dst:
        dst.write(np.zeros(fp.shape, dtype=np.float32), 1)
    with pytest.raises(ValueError, match="Outside-footprint pixels must all be NaN"):
        validate_submission_tif(zero_outside, tmpl)
    diagnostic = validate_submission_tif(zero_outside, tmpl, require_outside_nan=False)
    assert diagnostic["valid"] is True
    assert diagnostic["official_format_compliant"] is False


def test_generated_artifact_format_and_effective_uniqueness():
    report = json.loads((ROOT / "evidence" / "submission_validation_report.json").read_text())
    tmpl = ROOT / "data" / "sample_submission.tif"
    names = {
        "primary_allfinite": False,
        "primary_nanmask": True,
        "pure_physical_contender": False,
    }
    arrays = {}
    with rasterio.open(tmpl) as src:
        footprint = np.isfinite(src.read(1))

    prior = json.loads((ROOT / "evidence" / "group_forensic_audit.json").read_text())
    prior_shas = {row["sha256"] for row in prior["submissions"]}
    for key, outside_nan in names.items():
        cand = report["candidates"][key]
        tif_path = ROOT / "docs" / "downloads" / cand["filename"]
        assert tif_path.exists()
        v = validate_submission_tif(tif_path, tmpl, require_outside_nan=outside_nan)
        assert v["valid"] is True
        assert v["official_format_compliant"] is outside_nan
        assert v["in_footprint_nan_count"] == 0
        assert 0.0 <= v["in_footprint_min"] <= v["in_footprint_max"] <= 1.0
        assert v["sha256"] not in prior_shas
        with rasterio.open(tif_path) as src:
            arrays[key] = src.read(1)

    # Encoding twins must not be represented as two distinct experiments.
    assert np.array_equal(arrays["primary_allfinite"][footprint], arrays["primary_nanmask"][footprint])
    # The physical contender is materially different in-footprint.
    assert np.count_nonzero(arrays["primary_nanmask"][footprint] != arrays["pure_physical_contender"][footprint]) > 0


def test_h17_candidate_failed_gate_without_submission_slot():
    result = json.loads((ROOT / "evidence" / "hypothesis_h17_1_validation.json").read_text())
    assert result["status"] == "FAIL_HOLDOUT_GATE"
    assert result["submission_slot_spent"] is False
    assert result["submission_geotiff_created"] is False
    h16 = result["results"]["H16_1_current_holdout_best"]
    h17 = result["results"]["H17_1_candidate"]
    assert h17["mean_dense_dti"] < h16["mean_dense_dti"]
    assert h17["mean_sparse_dti"] < h16["mean_sparse_dti"]
    assert result["gate"]["candidate_sparse_fold_wins"] == 0


def test_public_docs_report_status_and_sources():
    index_html = (ROOT / "docs" / "index.html").read_text()
    exec_html = (ROOT / "docs" / "executive_summary.html").read_text()
    readme = (ROOT / "README.md").read_text()
    hypotheses = (ROOT / "docs" / "research" / "hypothesis_register.md").read_text()
    report = json.loads((ROOT / "evidence" / "submission_validation_report.json").read_text())
    lb = json.loads((ROOT / "docs" / "leaderboard.json").read_text())

    b16 = report["candidates"]["primary_nanmask"]
    assert b16["filename"] in index_html
    assert b16["filename"] in exec_html
    assert b16["validation"]["sha256"][:8] in index_html
    assert "0.3168" in index_html and "0.3168" in exec_html
    assert "0.1563" in index_html and "same" in readme.lower()
    assert "Standing project brief" in readme
    assert "H17-1" in hypotheses and "USGS" in hypotheses
    assert "FAIL_HOLDOUT_GATE" in (ROOT / "evidence" / "hypothesis_h17_1_validation.json").read_text()
    assert lb["live_drivendata_top5"][0]["dti"] == 0.3168
