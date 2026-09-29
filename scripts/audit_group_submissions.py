"""Forensic byte-and-pixel audit of 19 recorded submission artifacts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EVIDENCE_DIR = ROOT / "evidence"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


SUBMISSIONS = [
    {
        "repo": "GEMSDOE1",
        "site_url": "https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/GEMSDOE",
        "account": "extradr19",
        "score": 0.1563,
        "label": "ens12-adopted-floor0.1-w0 (CNN 12-model ensemble)",
        "path": "/tmp/audit/GEMSDOE/data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif",
    },
    {
        "repo": "5GEMSDOE",
        "site_url": "https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/5GEMSDOE",
        "account": "extradr19 / SDCF9",
        "score": 0.1563,
        "label": "ens12-adopted-floor0.1-w0 (Exact byte duplicate of GEMSDOE1)",
        "path": "/tmp/audit/5GEMSDOE/data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif",
    },
    {
        "repo": "8GEMSDOE",
        "site_url": "https://buffedlizard55-lab.github.io/8GEMSDOE/",
        "repo_url": "https://github.com/buffedlizard55-lab/8GEMSDOE",
        "account": "SDCF9 / smashi34",
        "score": 0.1563,
        "label": "8GEMSDOE_Hedge-v2 == max(ens12_7f00890a, catalogue)",
        "path": "/tmp/audit/8GEMSDOE/docs/downloads/8GEMSDOE_Hedge-v2_submission.tif",
    },
    {
        "repo": "GEMSDOE2",
        "site_url": "https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/GEMSDOE2",
        "account": "smashi34",
        "score": 0.1560,
        "label": "gemsdoe2-dual-family-union-f68e590f (ens12 U extension-arm)",
        "path": "/tmp/audit/GEMSDOE2/docs/gemsdoe2-dual-family-union-f68e590f.tif",
    },
    {
        "repo": "7GEMSDOE",
        "site_url": "https://buffedlizard55-lab.github.io/7GEMSDOE/",
        "repo_url": "https://github.com/buffedlizard55-lab/7GEMSDOE",
        "account": "wbg1",
        "score": 0.1461,
        "label": "gems7-lidarscarp-ridge-top2pct-36c3a3f341c8 (1m 3DEP lidar scarp ridge-thinned)",
        "path": "/tmp/audit/7GEMSDOE/downloads/gems7-lidarscarp-ridge-top2pct-36c3a3f341c8.tif",
    },
    {
        "repo": "12GEMSDOE",
        "site_url": "https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/12GEMSDOE",
        "account": "SDCF9",
        "score": 0.1294,
        "label": "r7-nms3-dem10-scarp_0c9199f14e62 (multi25+H28+DEM10 5x5 NMS, NaN outside)",
        "path": "/tmp/audit/12GEMSDOE/docs/downloads/12GEMSDOE_r7-nms3-dem10-scarp_0c9199f14e62.tif",
    },
    {
        "repo": "12GEMSDOE (allfinite)",
        "site_url": "https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/12GEMSDOE",
        "account": "SDCF9",
        "score": 0.1294,
        "label": "r7-nms3-dem10-scarp_0c9199f14e62_allfinite (0.0 outside footprint)",
        "path": "/tmp/audit/12GEMSDOE/docs/downloads/12GEMSDOE_r7-nms3-dem10-scarp_0c9199f14e62_allfinite.tif",
    },
    {
        "repo": "GEMSDOE3 (#1)",
        "site_url": "https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/GEMSDOE3",
        "account": "smrtdoog5",
        "score": 0.1193,
        "label": "pindrop-v4-nodes-f347b70daa (1 · SUBMIT FIRST, Pindrop nodes)",
        "path": "/tmp/audit/GEMSDOE3/docs/downloads/pindrop-v4-nodes-20260925T152420Z-f347b70daa.tif",
    },
    {
        "repo": "GEMSDOE3 (#3)",
        "site_url": "https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/GEMSDOE3",
        "account": "SDCF9",
        "score": 0.1152,
        "label": "pindrop-v4-ridge-4e03fc9705 (3 · CONTROL · UPLOAD LAST, dense ridge)",
        "path": "/tmp/audit/GEMSDOE3/docs/downloads/pindrop-v4-ridge-20260925T152422Z-4e03fc9705.tif",
    },
    {
        "repo": "GEMSDOE10 (H20)",
        "site_url": "https://buffedlizard55-lab.github.io/GEMSDOE10/",
        "repo_url": "https://github.com/buffedlizard55-lab/GEMSDOE10",
        "account": "wbg1",
        "score": 0.0921,
        "label": "h20-dem10-scarp-thin-20260927T155223039488Z-ffc91a1686",
        "path": "/tmp/audit/GEMSDOE10/docs/downloads/gems10-h20-dem10-scarp-thin-20260927T155223039488Z-ffc91a1686.tif",
    },
    {
        "repo": "GEMSDOE3 (#2)",
        "site_url": "https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/GEMSDOE3",
        "account": "wbg1",
        "score": 0.0830,
        "label": "pindrop-v4-discovery-37f9d5b855 (2 · SUBMIT SECOND, catalogue-gap)",
        "path": "/tmp/audit/GEMSDOE3/docs/downloads/pindrop-v4-discovery-20260925T152423Z-37f9d5b855.tif",
    },
    {
        "repo": "15GEMSDOE",
        "site_url": "https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/15GEMSDOE",
        "account": "smashi34",
        "score": 0.0782,
        "label": "gems-tso1-20260929T005627Z-conj_alteration_mag",
        "path": "/tmp/audit/15GEMSDOE/docs/downloads/gems-tso1-20260929T005627Z-conj_alteration_mag.tif",
    },
    {
        "repo": "GEMSDOE10 (H16)",
        "site_url": "https://buffedlizard55-lab.github.io/GEMSDOE10/",
        "repo_url": "https://github.com/buffedlizard55-lab/GEMSDOE10",
        "account": "wbg1",
        "score": 0.0461,
        "label": "h16-continuation-20260927T065521077735Z-3431b83c7c",
        "path": "/tmp/audit/GEMSDOE10/docs/downloads/gems10-h16-continuation-20260927T065521077735Z-3431b83c7c.tif",
    },
    {
        "repo": "GEMSDOE4",
        "site_url": "https://buffedlizard55-lab.github.io/GEMSDOE4/",
        "repo_url": "https://github.com/buffedlizard55-lab/GEMSDOE4",
        "account": "unrecorded",
        "score": 0.0343,
        "label": "gemsdoe4-combined-237f0063 (thick union blobs)",
        "path": "/tmp/audit/GEMSDOE4/data/evidence/combined/submission.tif",
    },
    {
        "repo": "6GEMSDOE",
        "site_url": "https://buffedlizard55-lab.github.io/6GEMSDOE/",
        "repo_url": "https://github.com/buffedlizard55-lab/6GEMSDOE",
        "account": "unrecorded",
        "score": 0.0286,
        "label": "gems6_hgb88-topk03_33cec71ff0 (near-catalogue HGB top-3%)",
        "path": "/tmp/audit/6GEMSDOE/downloads/gems6_hgb88-topk03_33cec71ff0.tif",
    },
    {
        "repo": "11GEMSDOE",
        "site_url": "https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/11GEMSDOE",
        "account": "unrecorded",
        "score": 0.0202,
        "label": "gems-structural-area06-v1 (near-catalogue structural area)",
        "path": "/tmp/audit/11GEMSDOE/docs/downloads/gems-structural-area06-v1.tif",
    },
    {
        "repo": "GEMSDOE9",
        "site_url": "https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/GEMSDOE9",
        "account": "unrecorded",
        "score": 0.0107,
        "label": "gemsdoe9-PLACEHOLDER-2314b599",
        "path": "/tmp/audit/GEMSDOE9/docs/downloads/gemsdoe9-PLACEHOLDER-2314b599.tif",
    },
    {
        "repo": "14GEMSDOE",
        "site_url": "https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html",
        "repo_url": "https://github.com/buffedlizard55-lab/14GEMSDOE",
        "account": "smrtdoog5",
        "score": 0.0020,
        "label": "GEMS_r5-geom-horse-ensemble_20260929T154852Z_ccbe1de0_site_e96e942f",
        "path": "/tmp/audit/14GEMSDOE/docs/downloads/GEMS_r5-geom-horse-ensemble_20260929T154852Z_ccbe1de0_site_e96e942f.tif",
    },
    {
        "repo": "13GEMSDOE",
        "site_url": "https://buffedlizard55-lab.github.io/13GEMSDOE/",
        "repo_url": "https://github.com/buffedlizard55-lab/13GEMSDOE",
        "account": "unscored",
        "score": None,
        "label": "13gems-composite-plus-20260929T183249Z_allfinite (unscored)",
        "path": "/tmp/audit/13GEMSDOE/docs/downloads/13gems-composite-plus-20260929T183249Z_allfinite.tif",
    },
]


def main() -> None:
    with rasterio.open(DATA_DIR / "sample_submission.tif") as src:
        footprint = np.isfinite(src.read(1))
    with rasterio.open(DATA_DIR / "labels.tif") as src:
        cat = (src.read(1) > 0) & footprint

    off_mask = footprint & (~cat)
    dist_to_cat = distance_transform_edt(~cat)
    rows = []
    cached_arrays = {}
    for item in SUBMISSIONS:
        p = Path(item["path"])
        sha = sha256_file(p)
        with rasterio.open(p) as src:
            arr = src.read(1)
        cached_arrays[item["repo"]] = arr
        out_vals = arr[~footprint]
        out_nan = bool(np.isnan(out_vals).all())
        pos = (arr > 0.5) & footprint
        on_cat = pos & cat
        off_cat = pos & (~cat)

        d_le3 = int((off_cat & (dist_to_cat <= 3.0)).sum())
        d_4_15 = int((off_cat & (dist_to_cat > 3.0) & (dist_to_cat <= 15.0)).sum())
        d_gt15 = int((off_cat & (dist_to_cat > 15.0)).sum())

        edt = distance_transform_edt(~off_cat)
        reach_300m_pct = round(100.0 * float((edt[off_mask] < 3.0).mean()), 2)

        rows.append(
            {
                "repo": item["repo"],
                "site_url": item["site_url"],
                "repo_url": item["repo_url"],
                "account": item["account"],
                "score": item["score"],
                "label": item["label"],
                "sha256": sha,
                "sha8": sha[:8],
                "bytes": p.stat().st_size,
                "positive_pixels": int(pos.sum()),
                "on_catalogue_pixels": int(on_cat.sum()),
                "off_catalogue_pixels": int(off_cat.sum()),
                "off_cat_dist_le_300m": d_le3,
                "off_cat_dist_300m_to_1500m": d_4_15,
                "off_cat_dist_gt_1500m": d_gt15,
                "frac_off_cat_gt_1500m": round(d_gt15 / max(float(off_cat.sum()), 1.0), 4),
                "reach_300m_pct": reach_300m_pct,
                "outside_nan": out_nan,
            }
        )

    # Verify exact identities
    g1_pos = (cached_arrays["GEMSDOE1"] > 0.5) & footprint
    g5_pos = (cached_arrays["5GEMSDOE"] > 0.5) & footprint
    g8_pos = (cached_arrays["8GEMSDOE"] > 0.5) & footprint
    g12_nan_pos = (cached_arrays["12GEMSDOE"] > 0.5) & footprint
    g12_fin_pos = (cached_arrays["12GEMSDOE (allfinite)"] > 0.5) & footprint
    g7_pos = (cached_arrays["7GEMSDOE"] > 0.5) & off_mask

    edt_g1 = distance_transform_edt(~(g1_pos & off_mask))
    g7_outside_g1_300m = int((g7_pos & (edt_g1 > 3.0)).sum())

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "interpretation_scope": "File identity, pixel counts, and spatial distribution relative to the local catalogue are descriptive. The reported DTI scores are not inverted into hidden-test true positives or recall.",
        "identities_verified": {
            "GEMSDOE1_equals_5GEMSDOE_bytes": rows[0]["sha256"] == rows[1]["sha256"],
            "GEMSDOE1_5GEMSDOE_shared_sha256": rows[0]["sha256"],
            "8GEMSDOE_equals_max_GEMSDOE1_and_catalogue": bool(
                np.array_equal(g8_pos, g1_pos | cat)
            ),
            "8GEMSDOE_off_catalogue_equals_GEMSDOE1_off_catalogue": bool(
                np.array_equal(g8_pos & off_mask, g1_pos & off_mask)
            ),
            "12GEMSDOE_nan_equals_allfinite_in_footprint": bool(
                np.array_equal(g12_nan_pos, g12_fin_pos)
            ),
            "7GEMSDOE_lidar_pixels_gt_300m_from_GEMSDOE1": g7_outside_g1_300m,
            "7GEMSDOE_lidar_fraction_gt_300m_from_GEMSDOE1": round(
                g7_outside_g1_300m / float(g7_pos.sum()), 4
            ),
        },
        "interpretation_limits": [
            "GEMSDOE1 and 5GEMSDOE contain identical prediction bytes, so their reported equal scores are duplicate submissions rather than independent method results.",
            "8GEMSDOE differs from ens12 only on pixels overlapping the local known catalogue. Its reported equal four-decimal score is consistent with catalogue neutrality but does not prove the evaluator rule.",
            "NaN-outside and zero-outside variants with the same in-footprint values are not scientifically distinct. The official submission format requires null/NaN outside bounds; zero-outside files are diagnostic only.",
            "Per-file counts and distances to the local catalogue are descriptive spatial statistics. Public DTI scores cannot be inverted to true positives or recall without hidden truth and full scoring details.",
            "A relationship between catalogue-distance distributions and reported scores is observational; it does not establish the hidden faults' geography or the cause of any score."
        ],
        "submissions": rows,
    }

    out_path = EVIDENCE_DIR / "group_forensic_audit.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Wrote forensic audit of {len(rows)} submissions -> {out_path}")


if __name__ == "__main__":
    main()
