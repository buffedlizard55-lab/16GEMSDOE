"""Build the submission-ready candidates, verify them, and publish the site manifest.

For every candidate this script
  1. builds a binary thin-ridge prediction from a score surface (real-task information rule: all catalogue faults known),
     removes pixels on known faults (they are masked by the evaluator, so they can never score),
  2. writes the official-format file (NaN outside the footprint, template raster profile) and an all-finite twin,
  3. re-reads the files and runs every check variant in ``gems.submission.check_variants``,
  4. runs the uniqueness gate against every file in ``registry/submissions.json`` and the other candidates,
  5. attaches the holdout evidence / gate status and a short truthful DrivenData note,
  6. writes ``docs/data/submissions.json`` (single source of truth for the site).

No score is predicted or claimed.  Output files are named with the hash of their *scored content*, so identical
predictions get identical ids regardless of container or nodata encoding.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt
from skimage.morphology import skeletonize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import forensics as F  # noqa: E402
from gems.holdout import Holdout  # noqa: E402
from gems.hypotheses import endpoint_junction_density  # noqa: E402
from gems.paths import DATA_DIR, DOWNLOADS_DIR, EVIDENCE_DIR, GROUP_DIR, LABELS_PATH, SITE_DATA_DIR, TEMPLATE_PATH  # noqa: E402
from gems.submission import (  # noqa: E402
    check_variants, make_filename, make_note, scored_content_id, write_submission, zip_single,
)

TODAY = datetime.now(timezone.utc).strftime("%Y%m%d")
DATE_RE = re.compile(r"-(\d{8})-[0-9a-f]{8}-")


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short=10", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> None:
    with rasterio.open(TEMPLATE_PATH) as s:
        footprint = np.isfinite(s.read(1))
    with rasterio.open(LABELS_PATH) as s:
        labels = (s.read(1) > 0) & footprint
    grid = F.Grid.load(TEMPLATE_PATH, LABELS_PATH)
    H = Holdout(footprint, labels)
    cache = DATA_DIR / "cache"
    oof = np.load(cache / "oof_probs_h16_1.npz")
    p_h16_1 = oof["h16_1"].astype(np.float32)
    h18 = json.loads((EVIDENCE_DIR / "hypothesis_h18_validation.json").read_text())
    base = json.loads((EVIDENCE_DIR / "spatial_holdout_results.json").read_text())["summary"]

    cplx_all = endpoint_junction_density(labels, footprint).ravel()[H.fp_idx]   # real task: every catalogue fault is known
    surfaces = {
        "h18-3a": p_h16_1 * (1.0 + cplx_all),
        "h16-1": p_h16_1,
    }
    # External-data candidate: USGS SGMC geologic-map faults >300 m from every catalogue fault, thinned to 1-px lines.
    with rasterio.open(ROOT / "evidence" / "ci" / "derived_sgmc_faults_100m_u8.tif") as s_:
        sgmc = (s_.read(1) == 1) & footprint
    sgmc_gap = skeletonize(sgmc & (distance_transform_edt(~labels) > 3.0)) & footprint
    sgmc_expl = json.loads((EVIDENCE_DIR / "hypothesis_h18_sgmc_exploratory.json").read_text())["arms"]["SGMC_gap_only"]

    cands = [
        {
            "key": "h18-3a", "hid": "H18-3a", "family": "gems16", "slug": "topo-geophys-x-complexity-prior",
            "note_summary": "topo+geophysics OOF surface x fault endpoint/junction prior, thin ridges 2.5%/quadrant",
            "title": "H16-1 surface × catalogue complexity prior",
            "one_liner": "Topography + geophysics detector (out-of-fold), boosted where known faults end or intersect at km scale; thin ridges, 2.5 % of pixels per quadrant.",
            "holdout_key": "H18_3a_complexity_prior",
            "holdout": h18["arms"]["H18_3a_complexity_prior"], "gate": h18["gate"]["H18_3a_complexity_prior"],
            "caveat": "Passed the pre-registered gate, but a plain fault-density prior gives almost the same lift (exploratory control), so the gain is "
                      "best explained by fault clustering, not by a structural-setting mechanism. The proxy rewards clustering by construction. "
                      "The holdout figure uses the quadrant-wise information rule; the published file applies the same operator with every catalogued fault known.",
        },
        {
            "key": "h16-1", "hid": "H16-1", "family": "gems16", "slug": "topo-geophys-baseline-ridges",
            "note_summary": "topo+geophysics OOF surface, thin ridges 2.5%/quadrant (holdout benchmark)",
            "title": "H16-1 surface (current holdout best)",
            "one_liner": "Topography + geophysics detector (out-of-fold), thin ridges, 2.5 % of pixels per quadrant. The benchmark every new idea must beat.",
            "holdout_key": "H16_1_SeamFree_MultiScale_Synthesis",
            "holdout": {k: base["H16_1_SeamFree_MultiScale_Synthesis"][k] for k in ("mean_dense_dti", "mean_sparse_dti", "fold_dense", "fold_sparse")},
            "gate": None,
            "caveat": "It is the benchmark itself, so it has no gate result; it has never been live-scored. Hidden-set performance is unknown.",
        },
        {
            "key": "sgmc-gap", "hid": "H18-4", "family": "gems16", "slug": "usgs-geologic-map-faults-gap",
            "note_summary": "USGS SGMC geologic-map faults >300 m from catalogue, 1-px lines (external-data probe)",
            "title": "USGS geologic-map faults absent from the catalogue (external data)",
            "one_liner": "Faults from the USGS State Geologic Map Compilation (Nevada and California) lying >300 m from every catalogue fault, thinned to 1-pixel lines. No model, no training.",
            "holdout_key": "SGMC_gap_only (exploratory)",
            "holdout": {k: sgmc_expl[k] for k in ("mean_dense_dti", "mean_sparse_dti", "fold_dense", "fold_sparse")},
            "gate": sgmc_expl["gate_vs_h16_1_informational"],
            "gate_eligible": False,
            "caveat": "NOT gate-eligible and needs an explicit owner decision: the holdout cannot measure whether geologic-map faults are NEW faults "
                      "(its hidden faults are Quaternary catalogue faults, which geologic maps include). SGMC is nominally 1:1,000,000, so positions may be hundreds of metres off. "
                      "Spending a slot on it is a measurement, not a validated bet.",
        },
    ]

    history = []
    for e in json.loads((ROOT / "registry" / "submissions.json").read_text())["entries"]:
        with rasterio.open(GROUP_DIR / f"{e['id']}.tif") as s:
            history.append({"id": e["id"], "array": s.read(1), "lb_score": e["lb_score"]})

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    prev_path = SITE_DATA_DIR / "submissions.json"
    prev = {c["key"]: c for c in json.loads(prev_path.read_text())["candidates"]} if prev_path.exists() else {}
    built = []
    for c in cands:
        pred = (sgmc_gap if c["key"] == "sgmc-gap" else (H.emit(surfaces[c["key"]]) & ~labels))   # known-fault pixels are masked: never scored
        pred_f = pred.astype(np.float32)
        cid = scored_content_id(pred_f, footprint, labels)
        date = TODAY                                   # unchanged content keeps its original date so rebuilds are idempotent
        old = prev.get(c["key"])
        if old and old["content_id"] == cid and (m := DATE_RE.search(old["files"]["tif"]["name"])):
            date = m.group(1)
        name_nan = make_filename(c["family"], f"{c['hid']}-{c['slug']}", date, cid, "nan")
        name_fin = make_filename(c["family"], f"{c['hid']}-{c['slug']}", date, cid, "allfinite")
        p_nan = write_submission(pred_f, TEMPLATE_PATH, DOWNLOADS_DIR / name_nan, outside="nan")
        p_fin = write_submission(pred_f, TEMPLATE_PATH, DOWNLOADS_DIR / name_fin, outside="zero")
        p_zip = zip_single(p_nan)
        chk_nan = check_variants(p_nan, TEMPLATE_PATH)
        chk_fin = check_variants(p_fin, TEMPLATE_PATH)
        for k in ("hard_failures",):
            assert not chk_nan[k] and not chk_fin[k], (c["key"], chk_nan[k], chk_fin[k])
        with rasterio.open(p_nan) as s:
            arr = s.read(1)
        gate_hist = F.gate_candidate(arr, grid, history + [{"id": "candidate:" + b["key"], "array": b["_arr"], "lb_score": None} for b in built])
        note = make_note(c["hid"], c["note_summary"], cid)
        built.append({
            "_arr": arr, "key": c["key"], "hid": c["hid"], "title": c["title"], "one_liner": c["one_liner"], "content_id": cid,
            "files": {
                "tif": {"name": name_nan, "bytes": p_nan.stat().st_size, "sha256": chk_nan["sha256"], "href": f"downloads/{name_nan}"},
                "zip": {"name": p_zip.name, "bytes": p_zip.stat().st_size, "sha256": F.sha256_bytes(p_zip.read_bytes()), "href": f"downloads/{p_zip.name}"},
                "tif_allfinite": {"name": name_fin, "bytes": p_fin.stat().st_size, "sha256": chk_fin["sha256"], "href": f"downloads/{name_fin}"},
            },
            "note": note,
            "checks_official_format": {k: v for k, v in chk_nan.items() if k != "checks"} | {"checks": {k: {"pass": v["pass"], "hard": v["hard_requirement"], "detail": v["detail"]} for k, v in chk_nan["checks"].items()}},
            "checks_allfinite_twin": {k: v for k, v in chk_fin.items() if k != "checks"} | {"checks": {k: {"pass": v["pass"], "hard": v["hard_requirement"], "detail": v["detail"]} for k, v in chk_fin["checks"].items()}},
            "uniqueness": gate_hist,
            "scored_pixels_predicted": int(pred.sum()),
            "share_of_footprint_pct": round(100.0 * pred.sum() / footprint.sum(), 3),
            "holdout": c["holdout"], "holdout_gate_vs_h16_1": c["gate"], "gate_eligible": c.get("gate_eligible", True), "caveat": c["caveat"],
        })
        print(f"{c['key']:<8} id={cid} scored_px={int(pred.sum()):,} uniqueness={gate_hist['verdict']} "
              f"nearest={[(n['id'], n['jaccard_positive']) for n in gate_hist['nearest'][:3]]}")

    # attach cross-candidate similarity (compute every pair before dropping the in-memory arrays)
    for b in built:
        b["similar_to_other_candidates"] = [
            {"key": o["key"], "jaccard_positive": F.pair_metrics(b["_arr"], o["_arr"], grid)["jaccard_positive"]} for o in built if o is not b
        ]
    for b in built:
        del b["_arr"]

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git_head(),
        "template_sha256": F.sha256_bytes(TEMPLATE_PATH.read_bytes()),
        "rolling_limit": "3 submissions per rolling 7-day window per entity (official rules 3.2/3.4; staff: forum topic 11524 post 2)",
        "claims": {
            "score_predicted": False,
            "statement": "No file has been live-scored. Holdout numbers recover KNOWN faults and cannot measure precision on the hidden NEW faults.",
        },
        "candidates": built,
    }
    keep = {Path(f["href"]).name for b in built for f in b["files"].values()}
    for stale in DOWNLOADS_DIR.iterdir():               # never leave superseded files that could be uploaded by mistake
        if stale.is_file() and stale.name not in keep:
            print("removing stale download", stale.name)
            stale.unlink()
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DATA_DIR / "submissions.json").write_text(json.dumps(manifest, indent=2, default=float) + "\n")
    (EVIDENCE_DIR / "submission_validation_report.json").write_text(json.dumps(manifest, indent=2, default=float) + "\n")
    print("wrote docs/data/submissions.json and evidence/submission_validation_report.json")


if __name__ == "__main__":
    main()
