"""Run the pre-registered H18 arms through the spatial holdout gate.

Protocol, constants and information rule are fixed in docs/research/preregistration_h18.md (committed before any result).
Output: evidence/hypothesis_h18_validation.json.  No submission slot is spent and no submission GeoTIFF is produced.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.holdout import Holdout, gate  # noqa: E402
from gems.hypotheses import (  # noqa: E402
    endpoint_junction_density,
    oblique_boost,
    product_of_experts,
    seam_free_calibrate,
)
from gems.paths import DATA_DIR, EVIDENCE_DIR, LABELS_PATH, TEMPLATE_PATH  # noqa: E402
from gems.validator import sha256_file  # noqa: E402

PREREG_COMMIT = "6c5f74a"


def main() -> None:
    t0 = time.time()
    with rasterio.open(TEMPLATE_PATH) as s:
        footprint = np.isfinite(s.read(1))
    with rasterio.open(LABELS_PATH) as s:
        labels = (s.read(1) > 0) & footprint
    H = Holdout(footprint, labels)
    fp_idx = H.fp_idx
    cache = DATA_DIR / "cache"
    arms = np.load(cache / "oof_probs_all_arms.npz")
    h16 = np.load(cache / "oof_probs_h16_1.npz")
    feats = np.load(cache / "features_fp.npz")
    lid_ok = feats["lid1m_valid"] > 0.5
    fold_fp = H.fold_2d.ravel()[fp_idx]

    base = H.evaluate(h16["h16_1"])            # must reproduce the committed H16-1 numbers
    committed = json.loads((EVIDENCE_DIR / "spatial_holdout_results.json").read_text())["summary"]["H16_1_SeamFree_MultiScale_Synthesis"]
    assert base["fold_dense"] == committed["fold_dense"] and base["fold_sparse"] == committed["fold_sparse"], "evaluator drift"
    print(f"[baseline] H16-1 reproduced: dense {base['mean_dense_dti']} sparse {base['mean_sparse_dti']}")

    results = {}

    # ---- H18-1: product of experts -----------------------------------------------------------------
    poe = product_of_experts([arms["H16_3_ScarpPure_1m_10m"], arms["Baseline_Bands19_DeReg"]])
    poe = seam_free_calibrate(poe, lid_ok, fold_fp)
    results["H18_1_PoE_scarp_x_geophysics"] = H.evaluate(poe)
    print("[H18-1] ", results["H18_1_PoE_scarp_x_geophysics"]["mean_dense_dti"], results["H18_1_PoE_scarp_x_geophysics"]["mean_sparse_dti"])

    # ---- H18-3: catalogue-geometry priors on the H16-1 surface ----------------------------------------
    p0 = h16["h16_1"].astype(np.float32)
    cplx_cache, strike_cache = {}, {}

    def complexity(f_id: int, mode: str) -> np.ndarray:
        key = (f_id, mode)
        if key not in cplx_cache:
            cplx_cache[key] = endpoint_junction_density(H.known_for(f_id, mode), footprint).ravel()[fp_idx]
        return cplx_cache[key]

    def boost_b(f_id: int, mode: str) -> np.ndarray:
        key = (f_id, mode)
        if key not in strike_cache:
            strike_cache[key] = oblique_boost(H.to_2d(p0), H.known_for(f_id, mode), footprint, mu=1.0).ravel()[fp_idx]
        return strike_cache[key]

    def surf_a(f_id: int, mode: str) -> np.ndarray:
        return p0 * (1.0 + 1.0 * complexity(f_id, mode))

    def surf_b(f_id: int, mode: str) -> np.ndarray:
        return p0 * boost_b(f_id, mode)

    def surf_c(f_id: int, mode: str) -> np.ndarray:
        return p0 * (1.0 + 1.0 * complexity(f_id, mode)) * boost_b(f_id, mode)

    for name, fn in (("H18_3a_complexity_prior", surf_a), ("H18_3b_oblique_prior", surf_b), ("H18_3c_both", surf_c)):
        t = time.time()
        results[name] = H.evaluate_by_quadrant(fn)
        print(f"[{name}] {results[name]['mean_dense_dti']} {results[name]['mean_sparse_dti']} ({time.time()-t:.0f}s)")

    verdicts = {name: gate(r, base) for name, r in results.items()}
    for name, v in verdicts.items():
        print(f"  gate {name}: {'PASS' if v['passed'] else 'FAIL'} dDense={v['delta_mean_dense']:+.5f} dSparse={v['delta_mean_sparse']:+.5f} "
              f"sparse_wins={v['sparse_fold_wins']}/4 worst(d/s)={v['worst_fold_delta_dense']}/{v['worst_fold_delta_sparse']}")

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "preregistration": {"file": "docs/research/preregistration_h18.md", "git_commit_before_results": PREREG_COMMIT},
        "status": "PASS" if any(v["passed"] for v in verdicts.values()) else "FAIL_ALL_ARMS",
        "submission_slot_spent": False,
        "submission_geotiff_created": False,
        "evaluation_scope": "Four-quadrant spatial holdout on the KNOWN catalogue plus the 20%-of-components sparse proxy. "
                            "Not hidden-test performance; a pass is necessary, not sufficient, evidence.",
        "implementation_details_not_in_preregistration": {
            "oblique_prior_neutral_default": "boost = 1.0 where the smoothed structure-tensor trace of known faults is < 2% of its 99th percentile",
            "h18_1_sum_not_mean": "log-odds are summed (literal PoE), then passed through a sigmoid",
        },
        "baseline": {"name": "H16_1_SeamFree_MultiScale_Synthesis", "reproduced_exactly": True,
                     **{k: base[k] for k in ("mean_dense_dti", "mean_sparse_dti", "fold_dense", "fold_sparse")}},
        "arms": results,
        "gate": verdicts,
        "input_sha256": {"training_features.tif": sha256_file(DATA_DIR / "training_features.tif"),
                         "labels.tif": sha256_file(LABELS_PATH), "sample_submission.tif": sha256_file(TEMPLATE_PATH)},
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    (EVIDENCE_DIR / "hypothesis_h18_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote evidence/hypothesis_h18_validation.json  status={report['status']}  ({report['elapsed_seconds']}s)")


if __name__ == "__main__":
    main()
