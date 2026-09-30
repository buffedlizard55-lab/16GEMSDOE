"""SENSITIVITY check: does the H18 verdict depend on how predictions on masked known-fault pixels are treated?

Registered rule  : predictions on known-fault pixels are neutral for false positives but can still earn true-positive credit.
Strict rule      : those predictions are dropped entirely (staff: it "should not matter whether known faults are included").
Runs on the registered sparse proxy and on 5 re-drawn proxies.  Output: evidence/hypothesis_h18_sensitivity.json (post-hoc).
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
from gems.hypotheses import endpoint_junction_density  # noqa: E402
from gems.paths import DATA_DIR, EVIDENCE_DIR, LABELS_PATH, TEMPLATE_PATH  # noqa: E402


def main() -> None:
    t0 = time.time()
    with rasterio.open(TEMPLATE_PATH) as s:
        fp = np.isfinite(s.read(1))
    with rasterio.open(LABELS_PATH) as s:
        lab = (s.read(1) > 0) & fp
    p0 = np.load(DATA_DIR / "cache" / "oof_probs_h16_1.npz")["h16_1"].astype(np.float32)
    idx = np.flatnonzero(fp.ravel())

    def density(known):
        d = gaussian_filter(known.astype(np.float32), 50.0)
        return np.clip(d / (float(np.percentile(d[fp], 99)) or 1.0), 0.0, 1.0).astype(np.float32)

    surf = {
        "H16_1_baseline": lambda H, f: p0,
        "H18_3a_complexity_prior": lambda H, f: p0 * (1.0 + endpoint_junction_density(H.known_for(f, "sparse"), fp).ravel()[idx]),
        "E2_plain_density_prior": lambda H, f: p0 * (1.0 + density(H.known_for(f, "sparse")).ravel()[idx]),
    }
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "POST_HOC_SENSITIVITY", "draws": {}}
    for draw in range(0, 6):
        H = Holdout(fp, lab, sparse_seed_offset=1000 * draw)
        base_emit = {f: H.emit_quadrant(p0, f) for f in range(4)}
        rec = {}
        for name, fn in surf.items():
            reg, strict = [], []
            for f in range(4):
                m = base_emit[f] if name == "H16_1_baseline" else H.emit_quadrant(fn(H, f), f)
                reg.append(H.score_quadrant(m, f, "sparse", mask_predictions=False))
                strict.append(H.score_quadrant(m, f, "sparse", mask_predictions=True))
            rec[name] = {"registered_rule": round(float(np.mean(reg)), 5), "strict_rule": round(float(np.mean(strict)), 5),
                         "fold_strict": [round(x, 5) for x in strict]}
        out["draws"][f"draw_{draw}" + ("_registered_seeds" if draw == 0 else "")] = rec
        print(f"draw {draw}: " + " | ".join(f"{k}: {v['registered_rule']:.4f}->{v['strict_rule']:.4f}" for k, v in rec.items()), flush=True)
    keys = list(surf)
    out["mean_over_6_draws"] = {k: {"registered_rule": round(float(np.mean([d[k]["registered_rule"] for d in out["draws"].values()])), 5),
                                    "strict_rule": round(float(np.mean([d[k]["strict_rule"] for d in out["draws"].values()])), 5)} for k in keys}
    out["draws_3a_beats_baseline_strict"] = int(sum(d["H18_3a_complexity_prior"]["strict_rule"] > d["H16_1_baseline"]["strict_rule"] for d in out["draws"].values()))
    out["draws_3a_beats_density_strict"] = int(sum(d["H18_3a_complexity_prior"]["strict_rule"] > d["E2_plain_density_prior"]["strict_rule"] for d in out["draws"].values()))
    out["elapsed_seconds"] = round(time.time() - t0, 1)
    (EVIDENCE_DIR / "hypothesis_h18_sensitivity.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["mean_over_6_draws"], indent=1), out["draws_3a_beats_baseline_strict"], out["draws_3a_beats_density_strict"], f"{out['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
