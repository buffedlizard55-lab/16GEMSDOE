"""POST-HOC / EXPLORATORY controls for the H18 pass (clearly NOT part of the pre-registered gate).

Purpose: decide whether the H18-3a pass reflects structural-setting physics or plain fault clustering, and whether it
survives re-drawn sparse proxies.  Output: evidence/hypothesis_h18_exploratory.json
  E1  parallel-strike prior (mirror of the failed oblique prior; post-hoc, generates a hypothesis for the NEXT round)
  E2  plain fault-density prior (control for H18-3a: same sigma/lambda, no endpoint/junction information)
  E3  five re-drawn sparse proxies (different random 20 % component subsets) for H16-1, H18-3a and E2
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.holdout import Holdout  # noqa: E402
from gems.hypotheses import endpoint_junction_density, local_strike_field, ridge_strike  # noqa: E402
from gems.paths import DATA_DIR, EVIDENCE_DIR, LABELS_PATH, TEMPLATE_PATH  # noqa: E402


def density(known: np.ndarray, footprint: np.ndarray, sigma_px: float = 50.0) -> np.ndarray:
    d = gaussian_filter(known.astype(np.float32), sigma_px)
    return np.clip(d / (float(np.percentile(d[footprint], 99)) or 1.0), 0.0, 1.0).astype(np.float32)


def main() -> None:
    t0 = time.time()
    with rasterio.open(TEMPLATE_PATH) as s:
        fp = np.isfinite(s.read(1))
    with rasterio.open(LABELS_PATH) as s:
        lab = (s.read(1) > 0) & fp
    H = Holdout(fp, lab)
    idx = H.fp_idx
    p0 = np.load(DATA_DIR / "cache" / "oof_probs_h16_1.npz")["h16_1"].astype(np.float32)
    out: dict = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "status": "EXPLORATORY_POST_HOC_NOT_GATE_ELIGIBLE", "arms": {}, "resampled_sparse": {}}

    def parallel_boost(Hh, f_id, mode):
        known = Hh.known_for(f_id, mode)
        k_strike, trace = local_strike_field(known, 100.0)
        r_strike = ridge_strike(Hh.to_2d(p0))
        boost = 1.0 + np.cos(r_strike - k_strike) ** 2
        info = trace > 0.02 * float(np.percentile(trace[fp], 99))
        return np.where(info, boost, 1.0).astype(np.float32).ravel()[idx]

    arms = {
        "E1_parallel_prior": lambda Hh, f, m: p0 * parallel_boost(Hh, f, m),
        "E2_plain_density_prior": lambda Hh, f, m: p0 * (1.0 + density(Hh.known_for(f, m), fp).ravel()[idx]),
        "H18_3a_complexity_prior": lambda Hh, f, m: p0 * (1.0 + endpoint_junction_density(Hh.known_for(f, m), fp).ravel()[idx]),
    }
    for name, fn in arms.items():
        r = H.evaluate_by_quadrant(lambda f, m, fn=fn: fn(H, f, m))
        out["arms"][name] = r
        print(f"[{name}] dense {r['mean_dense_dti']} sparse {r['mean_sparse_dti']} folds_sparse {r['fold_sparse']}")

    # E3: re-drawn sparse proxies (sparse mode only; 5 draws)
    for rep in range(1, 6):
        Hr = Holdout(fp, lab, sparse_seed_offset=1000 * rep)
        row = {"H16_1_baseline": float(np.mean([Hr.score_quadrant(Hr.emit_quadrant(p0, f), f, "sparse") for f in range(4)]))}
        for name in ("H18_3a_complexity_prior", "E2_plain_density_prior", "E1_parallel_prior"):
            fn = arms[name]
            row[name] = float(np.mean([Hr.score_quadrant(Hr.emit_quadrant(fn(Hr, f, "sparse"), f), f, "sparse") for f in range(4)]))
        out["resampled_sparse"][f"draw_{rep}"] = {k: round(v, 5) for k, v in row.items()}
        print(f"[draw {rep}]", out["resampled_sparse"][f"draw_{rep}"])
    keys = ["H16_1_baseline", "H18_3a_complexity_prior", "E2_plain_density_prior", "E1_parallel_prior"]
    out["resampled_sparse_summary"] = {
        k: {"mean": round(float(np.mean([d[k] for d in out["resampled_sparse"].values()])), 5),
            "sd": round(float(np.std([d[k] for d in out["resampled_sparse"].values()], ddof=1)), 5)} for k in keys}
    out["draws_where_3a_beats_baseline"] = int(sum(d["H18_3a_complexity_prior"] > d["H16_1_baseline"] for d in out["resampled_sparse"].values()))
    out["draws_where_3a_beats_plain_density"] = int(sum(d["H18_3a_complexity_prior"] > d["E2_plain_density_prior"] for d in out["resampled_sparse"].values()))
    out["elapsed_seconds"] = round(time.time() - t0, 1)
    (EVIDENCE_DIR / "hypothesis_h18_exploratory.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["resampled_sparse_summary"], indent=1), out["draws_where_3a_beats_baseline"], out["draws_where_3a_beats_plain_density"], f"{out['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
