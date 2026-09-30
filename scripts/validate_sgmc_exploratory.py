"""EXPLORATORY: USGS SGMC geologic-map faults as a catalogue-gap prior, scored on the spatial holdout.

Needs ``evidence/ci/derived_sgmc_faults_100m_u8.tif`` (produced by the CI job from the official USGS SGMC state shapefiles).
Information rule: SGMC is external map data (no labels).  Its pixels within 3 px (300 m) of the faults the evaluator may
treat as KNOWN for that quadrant are removed (they would be catalogue duplicates, displaced by map generalisation).
BIAS WARNING: the holdout's hidden faults are Quaternary catalogue faults, which geologic maps tend to include, so this
proxy overstates SGMC's value for truly NEW faults.  Output: evidence/hypothesis_h18_sgmc_exploratory.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.holdout import Holdout, gate  # noqa: E402
from gems.paths import DATA_DIR, EVIDENCE_DIR, LABELS_PATH, TEMPLATE_PATH  # noqa: E402


def main() -> None:
    with rasterio.open(TEMPLATE_PATH) as s:
        fp = np.isfinite(s.read(1))
    with rasterio.open(LABELS_PATH) as s:
        lab = (s.read(1) > 0) & fp
    with rasterio.open(ROOT / "evidence" / "ci" / "derived_sgmc_faults_100m_u8.tif") as s:
        sg = (s.read(1) == 1) & fp
    H = Holdout(fp, lab)
    p0 = np.load(DATA_DIR / "cache" / "oof_probs_h16_1.npz")["h16_1"].astype(np.float32)
    base = H.evaluate(p0)
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "EXPLORATORY_NOT_GATE_ELIGIBLE",
           "bias_warning": "Hidden faults in the proxy are Quaternary catalogue faults that geologic maps tend to include; real new faults may differ.",
           "sgmc_fault_pixels_in_footprint": int(sg.sum()), "baseline_h16_1": {k: base[k] for k in ("mean_dense_dti", "mean_sparse_dti", "fold_dense", "fold_sparse")}}
    res = {"SGMC_all_pixels": {"dense": [], "sparse": []}, "SGMC_gap_only": {"dense": [], "sparse": []},
           "H16_1_union_SGMC_gap": {"dense": [], "sparse": []}}
    sizes = {"SGMC_gap_only": [], "H16_1_union_SGMC_gap": []}
    for f in range(4):
        _f, _n, f_mask, _sl, _td, _ts, _kc, _fm = H.quads[f]
        h_emit = H.emit_quadrant(p0, f)
        for mode in ("dense", "sparse"):
            known = H.known_for(f, mode)
            near = distance_transform_edt(~known) <= 3.0
            gap = sg & ~near & f_mask
            res["SGMC_all_pixels"][mode].append(H.score_quadrant(sg & f_mask, f, mode))
            res["SGMC_gap_only"][mode].append(H.score_quadrant(gap, f, mode))
            res["H16_1_union_SGMC_gap"][mode].append(H.score_quadrant(h_emit | gap, f, mode))
            if mode == "sparse":
                sizes["SGMC_gap_only"].append(int(gap.sum()))
                sizes["H16_1_union_SGMC_gap"].append(int((h_emit | gap).sum()))
    out["arms"] = {}
    for name, d in res.items():
        r = {"mean_dense_dti": round(float(np.mean(d["dense"])), 5), "mean_sparse_dti": round(float(np.mean(d["sparse"])), 5),
             "fold_dense": [round(x, 5) for x in d["dense"]], "fold_sparse": [round(x, 5) for x in d["sparse"]]}
        out["arms"][name] = r
        out["arms"][name]["gate_vs_h16_1_informational"] = gate(r, base)
        print(f"{name:<24} dense {r['mean_dense_dti']} sparse {r['mean_sparse_dti']} folds_sparse {r['fold_sparse']}")
    out["emitted_pixels_sparse_mode_per_quadrant"] = sizes
    (EVIDENCE_DIR / "hypothesis_h18_sgmc_exploratory.json").write_text(json.dumps(out, indent=2) + "\n")
    print("baseline", base["mean_dense_dti"], base["mean_sparse_dti"], "| sizes", sizes)


if __name__ == "__main__":
    main()
