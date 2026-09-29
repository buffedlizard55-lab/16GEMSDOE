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
    """Verify that adding known-catalogue pixels under catalogue_mask leaves DTI unchanged
    (reproducing the live-leaderboard identity 8GEMSDOE = 0.1563 == GEMSDOE1 = 0.1563)."""
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


def test_generated_16gemsdoe_submissions_and_evidence():
    report_path = ROOT / "evidence" / "submission_validation_report.json"
    holdout_path = ROOT / "evidence" / "spatial_holdout_results.json"
    forensic_path = ROOT / "evidence" / "group_forensic_audit.json"
    data_ver_path = ROOT / "evidence" / "data_verification.json"

    assert report_path.exists()
    assert holdout_path.exists()
    assert forensic_path.exists()
    assert data_ver_path.exists()

    report = json.loads(report_path.read_text())
    holdout = json.loads(holdout_path.read_text())
    forensic = json.loads(forensic_path.read_text())

    # Verify H16-1 beats baseline and all individual hypotheses on both dense and sparse 4-fold holdout
    s_h1 = holdout["summary"]["H16_1_SeamFree_MultiScale_Synthesis"]
    s_base = holdout["summary"]["Baseline_Bands19_DeReg"]
    s_g7 = holdout["summary"]["Sibling_7GEMSDOE_LidarOnly_36c3a3f3"]
    assert s_h1["mean_dense_dti"] > s_base["mean_dense_dti"]
    assert s_h1["mean_sparse_dti"] > s_base["mean_sparse_dti"]
    assert s_h1["mean_dense_dti"] > s_g7["mean_dense_dti"]
    assert s_h1["mean_sparse_dti"] > s_g7["mean_sparse_dti"]

    # Verify all 3 generated .tif files exist, pass strict validation, and are unique vs all 19 prior subs
    prior_shas = {r["sha256"] for r in forensic["submissions"]}
    tmpl = ROOT / "data" / "sample_submission.tif"
    for key, outside_nan in [
        ("primary_allfinite", False),
        ("primary_nanmask", True),
        ("pure_physical_contender", False),
    ]:
        cand = report["candidates"][key]
        tif_path = ROOT / "docs" / "downloads" / cand["filename"]
        assert tif_path.exists()
        v = validate_submission_tif(tif_path, tmpl, require_outside_nan=outside_nan)
        assert v["valid"] is True
        assert v["in_footprint_nan_count"] == 0
        assert 0.0 <= v["in_footprint_min"] <= v["in_footprint_max"] <= 1.0
        assert v["sha256"] not in prior_shas


def test_docs_and_readme_synchronized_with_artifacts():
    report = json.loads((ROOT / "evidence" / "submission_validation_report.json").read_text())
    index_html = (ROOT / "docs" / "index.html").read_text()
    exec_html = (ROOT / "docs" / "executive_summary.html").read_text()
    readme_md = (ROOT / "README.md").read_text()
    lb_json = json.loads((ROOT / "docs" / "leaderboard.json").read_text())

    for key in ("primary_allfinite", "primary_nanmask", "pure_physical_contender"):
        cand = report["candidates"][key]
        fname = cand["filename"]
        sha8 = cand["validation"]["sha256"][:8]
        note = cand["drivendata_submission_note"]
        assert fname in index_html
        assert fname in exec_html
        assert fname in readme_md
        assert sha8 in index_html
        assert sha8 in readme_md
        assert note in index_html
        assert note in readme_md
        assert lb_json["submission_validation"]["candidates"][key]["validation"]["sha256"] == cand["validation"]["sha256"]

