"""Independent verification against OFFICIAL open-data sources (runs on GitHub-hosted runners; the agent sandbox cannot
reach these hosts).  Every step is isolated; a failed step is recorded, never fatal, and never fabricated.

Steps
  A  Official provenance of ``labels.tif``: rasterise the GDR INGENIOUS Quaternary-fault shapefiles (v1 and v2, DOI
     10.15121/1881483) on the competition grid and measure how well they reproduce ``labels.tif``.
  B  GDR thermal/hydrothermal point features (springs/wells, sinter/tufa, Quaternary volcanics, 2 m probes): counts in
     the GeoDAWN footprint and their distance to known faults (premise check for the "thermal anchor" hypothesis).
  C  USGS SGMC geologic-map faults (NV, CA): schema, positional scale caveat, overlap with the catalogue, and
     enrichment of our detectors' predicted pixels near off-catalogue SGMC faults versus a random-placement base rate.

Inputs that are fetched from the team's public GitHub (small): the competition grid/labels copy, ens12 and 7GEMSDOE
predictions.  No DrivenData host is contacted (DrivenData Terms of Use prohibit automated access).
Output: evidence/ci/external_verification.json
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import traceback
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "ci"
OUT.mkdir(parents=True, exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix="gems_ci_"))

RAW = "https://raw.githubusercontent.com/buffedlizard55-lab"
GDR = "https://gdr.openei.org/files/1391"
SRC = {
    "labels": f"{RAW}/GEMSDOE/main/data/bridge/existing_faults.tif",
    "template": f"{RAW}/GEMSDOE/main/data/bridge/example_submission.tif",
    "ens12": f"{RAW}/5GEMSDOE/main/data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif",
    "lidar7": f"{RAW}/7GEMSDOE/main/downloads/gems7-lidarscarp-ridge-top2pct-36c3a3f341c8.tif",
    "gdr_qfaults_v2": f"{GDR}/qfaults_ingenious_nad83conus117_2023-06-27.zip",
    "gdr_qfaults_v1": f"{GDR}/faults_quaternary_INGENIOUS_regional_data.zip",
    "gdr_wellspring": f"{GDR}/wellspringdata.gdb.zip",
    "gdr_paleo": f"{GDR}/paleo_geothermal_regional.zip",
    "gdr_volcanics": f"{GDR}/great_basin_q_volcanics.zip",
    "gdr_2m_probes": f"{GDR}/2m_temperature_probe_INGENIOUS_regional_data.zip",
    "sgmc_nv": "https://mrdata.usgs.gov/geology/state/shp/NV.zip",
    "sgmc_ca": "https://mrdata.usgs.gov/geology/state/shp/CA.zip",
}
report: dict = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "downloads": {}, "steps": {}}


def fetch(key: str) -> Path | None:
    url = SRC[key]
    dest = WORK / Path(url).name
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "16GEMSDOE-source-verification/1.0 (research; contact via repo)"})
        with urllib.request.urlopen(req, timeout=240) as r:
            data = r.read()
        dest.write_bytes(data)
        report["downloads"][key] = {"url": url, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "ok": True}
        return dest
    except Exception as exc:  # noqa: BLE001
        report["downloads"][key] = {"url": url, "ok": False, "error": repr(exc)[:300]}
        return None


def step(name):
    def deco(fn):
        def run(*a, **k):
            try:
                report["steps"][name] = fn(*a, **k)
            except Exception as exc:  # noqa: BLE001
                report["steps"][name] = {"ok": False, "error": repr(exc)[:400], "trace": traceback.format_exc()[-1500:]}
            print(f"[{name}] done: {str(report['steps'][name])[:300]}", flush=True)
        return run
    return deco


def main() -> None:
    import geopandas as gpd
    import rasterio
    from rasterio import features
    from scipy.ndimage import distance_transform_edt

    p_lab, p_tmp = fetch("labels"), fetch("template")
    if not (p_lab and p_tmp):
        report["fatal"] = "could not fetch competition-grid copy from GitHub"
        (OUT / "external_verification.json").write_text(json.dumps(report, indent=2) + "\n")
        return
    with rasterio.open(p_tmp) as s:
        footprint = np.isfinite(s.read(1)); transform, crs, shape = s.transform, s.crs, s.shape
    with rasterio.open(p_lab) as s:
        labels = (s.read(1) > 0) & footprint
    dist_cat = distance_transform_edt(~labels).astype(np.float32)
    n_lab = int(labels.sum())
    from shapely.geometry import box
    grid_box = box(243350, 4135550, 572550, 4508550)

    def read_any(zip_path: Path):
        """Read every layer in a zip (shapefile or file-gdb); return {layer_name: GeoDataFrame}."""
        import pyogrio
        ex = WORK / (zip_path.stem + "_x")
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(ex)
        out = {}
        cands = [p for p in ex.rglob("*") if p.suffix.lower() == ".shp"] + [p for p in ex.rglob("*.gdb") if p.is_dir()]
        for c in cands:
            try:
                if c.suffix.lower() == ".gdb":
                    for lname, _g in pyogrio.list_layers(c):
                        out[f"{c.name}:{lname}"] = gpd.read_file(c, layer=lname)
                else:
                    out[c.name] = gpd.read_file(c)
            except Exception as exc:  # noqa: BLE001
                out[f"{c.name}:ERROR"] = repr(exc)[:200]
        return out

    def to_utm(gdf):
        if gdf.crs is None:
            gdf = gdf.set_crs(4269)   # GDR states "NAD83 Geographic" for these shapefiles
        return gdf.to_crs(32611)

    def raster_lines(gdf, all_touched=False):
        shapes = [(g, 1) for g in gdf.geometry if g is not None and not g.is_empty]
        if not shapes:
            return np.zeros(shape, dtype=bool)
        return features.rasterize(shapes, out_shape=shape, transform=transform, all_touched=all_touched, dtype="uint8").astype(bool) & footprint

    def compare_to_labels(R):
        nR = int(R.sum())
        dR = distance_transform_edt(~R)
        out = {"raster_pixels": nR, "labels_pixels": n_lab, "exact_overlap_px": int((R & labels).sum())}
        for k in (0, 1, 2, 3):
            out[f"labels_within_{k}px_of_raster_frac"] = round(float((dR[labels] <= k).mean()), 4)
            out[f"raster_within_{k}px_of_labels_frac"] = round(float((dist_cat[R] <= k).mean()), 4) if nR else None
        return out

    # ---------------- A: labels provenance -----------------------------------------------------------------
    @step("A_labels_provenance_vs_GDR_qfaults")
    def step_a():
        res = {"ok": True, "official_source": "https://gdr.openei.org/submissions/1391 (DOI 10.15121/1881483)", "versions": {}}
        for key in ("gdr_qfaults_v2", "gdr_qfaults_v1"):
            zp = fetch(key)
            if not zp:
                res["versions"][key] = {"ok": False, "error": report["downloads"][key].get("error")}
                continue
            layers = read_any(zp)
            v = {"ok": True, "layers": {}}
            merged = None
            for lname, gdf in layers.items():
                if isinstance(gdf, str):
                    v["layers"][lname] = gdf
                    continue
                v["layers"][lname] = {"rows": int(len(gdf)), "crs": str(gdf.crs), "geom_types": sorted(gdf.geom_type.dropna().unique().tolist()),
                                      "columns": [c for c in gdf.columns][:25]}
                if gdf.geom_type.astype(str).str.contains("Line").any():
                    g = to_utm(gdf[gdf.geom_type.astype(str).str.contains("Line")])
                    g = g[g.intersects(grid_box)]
                    merged = g if merged is None else gpd.GeoDataFrame(__import__("pandas").concat([merged, g]), crs=32611)
            if merged is not None and len(merged):
                v["lines_in_grid_bounds"] = int(len(merged))
                v["all_touched_false"] = compare_to_labels(raster_lines(merged, False))
                v["all_touched_true"] = compare_to_labels(raster_lines(merged, True))
            res["versions"][key] = v
        return res

    step_a()

    # ---------------- B: thermal anchors --------------------------------------------------------------------
    @step("B_thermal_features")
    def step_b():
        res = {"ok": True, "datasets": {}}
        rng = np.random.default_rng(7)
        fp_rc = np.column_stack(np.nonzero(footprint))
        rand = fp_rc[rng.choice(len(fp_rc), 50000, replace=False)]
        rand_d = dist_cat[rand[:, 0], rand[:, 1]]
        res["random_footprint_pixels_distance_to_known_fault_px"] = {"p25": float(np.percentile(rand_d, 25)), "median": float(np.median(rand_d)),
                                                                    "p75": float(np.percentile(rand_d, 75)), "frac_within_10px_1km": float((rand_d <= 10).mean())}
        for key in ("gdr_wellspring", "gdr_paleo", "gdr_volcanics", "gdr_2m_probes"):
            zp = fetch(key)
            if not zp:
                res["datasets"][key] = {"ok": False, "error": report["downloads"][key].get("error")}
                continue
            layers = read_any(zp)
            dd = {"ok": True, "layers": {}}
            for lname, gdf in layers.items():
                if isinstance(gdf, str):
                    dd["layers"][lname] = gdf
                    continue
                info = {"rows": int(len(gdf)), "crs": str(gdf.crs), "geom_types": sorted(gdf.geom_type.dropna().unique().tolist()), "columns": list(gdf.columns)[:30]}
                try:
                    g = to_utm(gdf)
                    pts = g.geometry.representative_point()
                    r = ((4508550 - pts.y.values) / 100.0).astype(int)
                    c = ((pts.x.values - 243350) / 100.0).astype(int)
                    ok = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
                    inside = np.zeros(len(g), bool)
                    inside[ok] = footprint[r[ok], c[ok]]
                    info["in_footprint"] = int(inside.sum())
                    if inside.any():
                        d = dist_cat[r[inside], c[inside]]
                        info["distance_to_known_fault_px"] = {"p25": float(np.percentile(d, 25)), "median": float(np.median(d)), "p75": float(np.percentile(d, 75)),
                                                               "frac_within_10px_1km": round(float((d <= 10).mean()), 4), "frac_beyond_30px_3km": round(float((d > 30).mean()), 4)}
                except Exception as exc:  # noqa: BLE001
                    info["error"] = repr(exc)[:200]
                dd["layers"][lname] = info
            res["datasets"][key] = dd
        return res

    step_b()

    # ---------------- C: SGMC faults -------------------------------------------------------------------------
    @step("C_sgmc_faults")
    def step_c():
        res = {"ok": True, "source": "https://mrdata.usgs.gov/geology/state/ (SGMC; nominal scale 1:1,000,000 per ScienceBase item 5888bf4fe4b05ccb964bab9d)", "states": {}}
        merged = []
        for key in ("sgmc_nv", "sgmc_ca"):
            zp = fetch(key)
            if not zp:
                res["states"][key] = {"ok": False, "error": report["downloads"][key].get("error")}
                continue
            layers = read_any(zp)
            st = {"ok": True, "layers": {}}
            for lname, gdf in layers.items():
                if isinstance(gdf, str):
                    st["layers"][lname] = gdf
                    continue
                gt = sorted(gdf.geom_type.dropna().unique().tolist())
                info = {"rows": int(len(gdf)), "geom_types": gt, "columns": list(gdf.columns)[:30]}
                if any("Line" in t for t in gt):
                    for col in ("DESCRIPT", "SYMBOL", "MISC", "GEOM"):
                        if col in gdf.columns:
                            vc = gdf[col].astype(str).value_counts().head(40)
                            info[f"top_{col}"] = {str(k): int(v) for k, v in vc.items()}
                    txt_cols = [c for c in gdf.columns if c != "geometry" and str(gdf[c].dtype) in ("object", "str", "string")]
                    if txt_cols:
                        fault = gdf[txt_cols].apply(lambda s_: s_.astype(str).str.contains("fault|thrust", case=False, na=False)).any(axis=1)
                        info["rows_mentioning_fault_or_thrust"] = int(fault.sum())
                        if fault.any():
                            merged.append(to_utm(gdf[fault]))
                st["layers"][lname] = info
            res["states"][key] = st
        if merged:
            import pandas as pd
            allf = gpd.GeoDataFrame(pd.concat(merged), crs=32611)
            allf = allf[allf.intersects(grid_box)]
            R = raster_lines(allf, True)
            res["fault_lines_in_grid"] = int(len(allf))
            res["sgmc_fault_pixels_in_footprint"] = int(R.sum())
            res["sgmc_pixels_within_3px_of_catalogue_frac"] = round(float((dist_cat[R] <= 3).mean()), 4)
            res["catalogue_within_3px_of_sgmc_frac"] = round(float((distance_transform_edt(~R)[labels] <= 3).mean()), 4)
            off = R & ~labels & (dist_cat > 3)           # SGMC faults that are NOT at/near the known catalogue
            res["sgmc_off_catalogue_pixels_gt_3px"] = int(off.sum())
            d_off = distance_transform_edt(~off)
            scored = footprint & ~labels
            base = float((d_off[scored] < 3).mean())   # base rate: share of all scored pixels lying within 300 m of off-catalogue SGMC faults
            enr = {"base_rate_scored_pixels_within_300m_of_off_catalogue_sgmc": round(base, 4)}
            for key in ("ens12", "lidar7"):
                pp = fetch(key)
                if not pp:
                    continue
                with rasterio.open(pp) as s:
                    P = (np.nan_to_num(s.read(1), nan=0.0) > 0.5) & scored
                frac = float((d_off[P] < 3).mean())
                enr[key] = {"positive_scored_pixels": int(P.sum()), "frac_within_300m_of_off_catalogue_sgmc": round(frac, 4), "enrichment_ratio_vs_base_rate": round(frac / base, 3) if base else None}
            res["enrichment_of_detectors"] = enr
            out_tif = OUT / "derived_sgmc_faults_100m_u8.tif"
            prof = {"driver": "GTiff", "dtype": "uint8", "count": 1, "height": shape[0], "width": shape[1], "crs": crs, "transform": transform, "compress": "deflate", "nodata": 255}
            with rasterio.open(out_tif, "w", **prof) as dst:
                dst.write(np.where(footprint, R.astype(np.uint8), 255).astype(np.uint8), 1)
            res["derived_raster"] = {"path": str(out_tif.relative_to(ROOT)), "bytes": out_tif.stat().st_size}
        return res

    step_c()
    report["elapsed_note"] = "all steps executed on a GitHub-hosted runner"


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        report["fatal"] = repr(exc)
        report["trace"] = traceback.format_exc()[-2000:]
    (OUT / "external_verification.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print("wrote evidence/ci/external_verification.json")
    sys.exit(0)
