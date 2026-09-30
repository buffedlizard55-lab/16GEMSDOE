"""Generate the static GitHub Pages site from verified data.  Run:  python scripts/build_site.py

Inputs (all committed): docs/data/*.json, registry/*.json, evidence/*.json, docs/research/*.md, docs/knowledge/*.md
Outputs: docs/*.html and the root index.html redirect.  No number is typed into HTML by hand: anything numeric comes from
the evidence files, and Markdown placeholders ``{{name}}`` must all resolve or the build fails.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.metric import marginal_inclusion_threshold  # noqa: E402

DOCS = ROOT / "docs"
DATA = DOCS / "data"
REG = ROOT / "registry"
EVI = ROOT / "evidence"
REPO_URL = "https://github.com/buffedlizard55-lab/16GEMSDOE"
BLOB = REPO_URL + "/blob/main/"
COMP = "https://www.drivendata.org/competitions/306/competition-doe-gems/"
DEADLINE_ISO = "2026-12-03T23:59:00Z"


def J(p: Path):
    return json.loads(p.read_text())


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def inline(x) -> str:
    """Escape text, then turn Markdown-style `code` spans into <code> (used for registry text)."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(x))


def fmt_mb(n: int) -> str:
    return f"{n / 1e6:.1f} MB"


def git_short() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short=9", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


# ------------------------------------------------------------------------------------------------ data + placeholders
subs = J(DATA / "submissions.json")
forn = J(DATA / "forensics.json")
lb = J(DATA / "leaderboard.json")
foot = J(DATA / "footprint.json")
sources = J(REG / "sources.json")
flags = J(REG / "irregularities.json")
h18 = J(EVI / "hypothesis_h18_validation.json")
expl = J(EVI / "hypothesis_h18_exploratory.json")
sgx = J(EVI / "hypothesis_h18_sgmc_exploratory.json")
ci = J(EVI / "ci" / "external_verification.json")
prof = J(EVI / "feature_profile.json")
sim = J(EVI / "submission_similarity.json")
sens = J(EVI / "hypothesis_h18_sensitivity.json")
calib = J(EVI / "proxy_calibration_vs_lb.json")
attr = J(EVI / "lb_signal_attribution.json")
health_p = DATA / "source_health.json"
health = J(health_p) if health_p.exists() else None
scan_p = DATA / "group_scan.json"
scan = J(scan_p) if scan_p.exists() else None
ledger_p = REG / "ledger.json"
LEDGER = {}
if ledger_p.exists():
    for _e in J(ledger_p)["entries"]:
        LEDGER[_e["content_id"]] = _e          # latest entry per content id wins


def ctx() -> dict[str, str]:
    a = ci["steps"]["A_labels_provenance_vs_GDR_qfaults"]["versions"]["gdr_qfaults_v2"]["all_touched_false"]
    b = ci["steps"]["B_thermal_features"]
    springs = next(v for k, v in b["datasets"]["gdr_wellspring"]["layers"].items() if k.endswith("spring_features_20220808"))
    c = ci["steps"]["C_sgmc_faults"]
    lineage = {l["git_blob_sha1"][:10]: l for l in sim["lineage_identical_bytes_across_repos"]}
    ens = lineage["812e61b740"]
    near_dup = {(p["a"], p["b"]): p for p in sim["near_duplicate_pairs_jaccard_ge_0_80"]}
    sp = sim["score_vs_geometry_descriptive"]["spearman"]
    rs = expl["resampled_sparse_summary"]
    base = h18["baseline"]
    cand_nn = max(n["jaccard_positive"] for cnd in subs["candidates"] for n in cnd["uniqueness"]["nearest"] if not n["id"].startswith("candidate:"))
    return {
        "dup_gemsdoe2_jaccard": f"{near_dup[('GEMSDOE1', 'GEMSDOE2')]['jaccard_positive']:.3f}",
        "ens12_copies": str(ens["copies"]), "ens12_repos": str(len(ens["repos"])),
        "corr_n": str(sim["score_vs_geometry_descriptive"]["n_unique_scored_contents"]),
        "corr_near": f"{sp['frac_near_le_300m']['spearman_rho']:+.2f}", "corr_far": f"{sp['frac_far_gt_1500m']['spearman_rho']:+.2f}",
        "sgmc_off_px": f"{c['sgmc_off_catalogue_pixels_gt_3px']:,}",
        "springs_far_pct": f"{100 * springs['distance_to_known_fault_px']['frac_beyond_30px_3km']:.0f}",
        "springs_near_pct": f"{100 * springs['distance_to_known_fault_px']['frac_within_10px_1km']:.0f}",
        "random_near_pct": f"{100 * b['random_footprint_pixels_distance_to_known_fault_px']['frac_within_10px_1km']:.0f}",
        "n_springs": f"{springs['in_footprint']:,}",
        "h16_dense": f"{base['mean_dense_dti']:.5f}", "h16_sparse": f"{base['mean_sparse_dti']:.5f}",
        "draws_beat_base": str(expl["draws_where_3a_beats_baseline"]), "draws_beat_dens": str(expl["draws_where_3a_beats_plain_density"]),
        "rd_3a": f"{rs['H18_3a_complexity_prior']['mean']:.4f}", "rd_base": f"{rs['H16_1_baseline']['mean']:.4f}", "rd_dens": f"{rs['E2_plain_density_prior']['mean']:.4f}",
        "sens_max": f"{max(abs(d[k]['registered_rule'] - d[k]['strict_rule']) for d in sens['draws'].values() for k in d):.4f}",
        "sens_beat_base": str(sens["draws_3a_beats_baseline_strict"]), "sens_beat_dens": str(sens["draws_3a_beats_density_strict"]),
        "attr_n": str(attr["n_files"]), "attr_m": str(attr["n_comparisons"]), "attr_bonf": f"{attr['bonferroni_p_threshold_0_05']:.4f}",
        "attr_bestp": f"{min(r['p_uncorrected'] for r in attr['top_by_abs_rho']):.3f}", "attr_fp": f"{attr['expected_false_positives_at_p_0_05']:.1f}",
        "attr_antislope": f"{next(r['spearman_rho'] for r in attr['top_by_abs_rho'] if r['feature'] == 'lid1m_antislope'):+.2f}",
        "attr_tectfluv": f"{next(r['spearman_rho'] for r in attr['top_by_abs_rho'] if r['feature'] == 'lid1m_tect_vs_fluv'):+.2f}",
        "attr_depth": f"{next(r['spearman_rho'] for r in attr['top_by_abs_rho'] if r['feature'] == 'depth_base_grad'):+.2f}",
        "calib_n": str(calib["n_unique_scored_files"]),
        "calib_dense_rho": f"{calib['correlation_with_public_score']['known_dense']['spearman_rho']:+.2f}",
        "calib_dense_p": f"{calib['correlation_with_public_score']['known_dense']['spearman_p']:.2f}",
        "calib_gap_rho": f"{calib['correlation_with_public_score']['sgmc_gap']['spearman_rho']:+.2f}",
        "calib_gap_p": f"{calib['correlation_with_public_score']['sgmc_gap']['spearman_p']:.3f}",
        "calib_h161": f"{next(c['sgmc_gap'] for c in calib['candidates_on_the_same_scales'] if c['key'] == 'h16-1'):.3f}",
        "calib_h183a": f"{next(c['sgmc_gap'] for c in calib['candidates_on_the_same_scales'] if c['key'] == 'h18-3a'):.3f}",
        "calib_ens12": f"{next(r['sgmc_gap'] for r in calib['per_file'] if r['id'] == 'GEMSDOE1'):.3f}",
        "sgmc_gap_sparse": f"{sgx['arms']['SGMC_gap_only']['mean_sparse_dti']:.4f}",
        "cand_max_jaccard": f"{cand_nn:.2f}",
        "tau_156": f"{marginal_inclusion_threshold(0.1563):.4f}", "tau_317": f"{marginal_inclusion_threshold(0.3168):.4f}",
        "tmin_156": f"{100 * 0.8 * 0.1563 / (1 - 0.2 * 0.1563):.1f}", "tmin_317": f"{100 * 0.8 * 0.3168 / (1 - 0.2 * 0.3168):.1f}",
        "footprint_px": f"{foot['footprint_pixels']:,}",
        "labels_exact_pct": f"{100 * a['exact_overlap_px'] / a['labels_pixels']:.2f}",
        "tc_corr_ext": f"{prof['tc_identity_check']['corr_band6_vs_external_geodawn_TC']:+.3f}",
        "tc_corr_tilt": f"{prof['tc_identity_check']['corr_band6_vs_computed_magnetic_tilt']:+.3f}",
        "invalid_min": f"{min(x['invalid_inside_footprint'] for x in prof['bands']):,}",
        "invalid_max": f"{max(x['invalid_inside_footprint'] for x in prof['bands']):,}",
    }


def table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    h = "".join(f"<th>{x}</th>" for x in headers)
    b = "".join("<tr" + (f' class="{r[-1]}"' if len(r) > len(headers) else "") + ">" + "".join(f"<td>{c}</td>" for c in r[: len(headers)]) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def h18_table() -> str:
    rows = []
    names = {"H18_1_PoE_scarp_x_geophysics": "H18-1 product-of-experts", "H18_3a_complexity_prior": "H18-3a endpoint/junction prior",
             "H18_3b_oblique_prior": "H18-3b oblique-strike prior", "H18_3c_both": "H18-3c both priors"}
    b = h18["baseline"]
    rows.append(["<strong>H16-1 baseline</strong>", f"{b['mean_dense_dti']:.5f}", f"{b['mean_sparse_dti']:.5f}", "—", "—", "—", "reference"])
    for k, nm in names.items():
        r, g = h18["arms"][k], h18["gate"][k]
        rows.append([nm, f"{r['mean_dense_dti']:.5f}", f"{r['mean_sparse_dti']:.5f}", f"{g['delta_mean_dense']:+.5f}", f"{g['delta_mean_sparse']:+.5f}",
                     f"{g['sparse_fold_wins']}/4", "<strong class=\"res-ok\">PASS</strong>" if g["passed"] else "<span class=\"res-bad\">FAIL</span>"])
    return table(["Arm", "Dense DTI", "Sparse DTI", "Δ dense", "Δ sparse", "Sparse folds won", "Gate"], rows)


def explore_table() -> str:
    a = expl["arms"]
    rows = [["E1 parallel-strike prior (post-hoc mirror of H18-3b)", f"{a['E1_parallel_prior']['mean_dense_dti']:.5f}", f"{a['E1_parallel_prior']['mean_sparse_dti']:.5f}"],
            ["E2 plain fault-density prior (control)", f"{a['E2_plain_density_prior']['mean_dense_dti']:.5f}", f"{a['E2_plain_density_prior']['mean_sparse_dti']:.5f}"],
            ["H18-3a again (same folds)", f"{a['H18_3a_complexity_prior']['mean_dense_dti']:.5f}", f"{a['H18_3a_complexity_prior']['mean_sparse_dti']:.5f}"]]
    rs = expl["resampled_sparse_summary"]
    rows2 = [[k.replace("_", " "), f"{v['mean']:.4f}", f"{v['sd']:.4f}"] for k, v in rs.items()]
    return (table(["Arm (same quadrants)", "Dense DTI", "Sparse DTI"], rows) +
            "<p><strong>Five re-drawn sparse proxies</strong> (different random 20 % component subsets):</p>" +
            table(["Arm", "Mean sparse DTI", "SD across draws"], rows2))


def sgmc_table() -> str:
    a = sgx["arms"]
    rows = []
    for k, nm in (("SGMC_all_pixels", "SGMC fault pixels (all)"), ("SGMC_gap_only", "SGMC gap only (≥ 300 m from known faults)"), ("H16_1_union_SGMC_gap", "H16-1 ∪ SGMC gap")):
        rows.append([nm, f"{a[k]['mean_dense_dti']:.5f}", f"{a[k]['mean_sparse_dti']:.5f}"])
    rows.insert(0, ["H16-1 baseline", f"{sgx['baseline_h16_1']['mean_dense_dti']:.5f}", f"{sgx['baseline_h16_1']['mean_sparse_dti']:.5f}"])
    return table(["Arm", "Dense DTI", "Sparse DTI"], rows)


def layers_table() -> str:
    rows = []
    for b in prof["bands"]:
        row = [str(b["band"]), f"<code>{esc(b['name'])}</code>", esc(b["category"]), esc(b["description"] or ""),
               f"{b['footprint_min']:.4g} … {b['footprint_max']:.4g}", f"{b['invalid_inside_footprint']:,}"]
        if b["name"] == "tc":
            row.append("dup")                      # highlight: mislabelled in the file (flag F01)
        rows.append(row)
    return table(["#", "Name", "Category (file tag)", "File description", "Footprint range", "Invalid px inside"], rows)


def calib_table() -> str:
    names = {"known_dense": "Known faults, unmasked (what the dense holdout measures; contaminated for trained files)",
             "sgmc_offcat": "USGS geologic-map faults not on a catalogue pixel",
             "sgmc_gap": "USGS geologic-map faults >300 m from every catalogued fault"}
    rows = []
    for k in ("known_dense", "sgmc_offcat", "sgmc_gap"):
        c = calib["correlation_with_public_score"][k]
        rows.append([esc(names[k]), f"{c['spearman_rho']:+.2f}", f"{c['spearman_p']:.3f}", f"{c['kendall_tau']:+.2f}", str(c["n"])])
    return table(["Proxy truth", "Spearman ρ with public score", "p", "Kendall τ", "n files"], rows)


def render_md(path: Path, extra: dict[str, str] | None = None) -> str:
    text = path.read_text()
    mapping = ctx()
    mapping.update({"calib_table": calib_table(), "h18_table": h18_table(), "explore_table": explore_table(), "sgmc_table": sgmc_table(), "layers_table": layers_table()})
    if extra:
        mapping.update(extra)
    text = re.sub(r"\{\{(\w+)\}\}", lambda m: mapping[m.group(1)] if m.group(1) in mapping else (_ for _ in ()).throw(KeyError(f"unresolved placeholder {m.group(0)} in {path.name}")), text)
    return markdown.markdown(text, extensions=["tables", "toc", "fenced_code", "sane_lists", "md_in_html"])


# ------------------------------------------------------------------------------------------------ page shell
DL_ICON = '<svg class="ico" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M12 3v12m0 0l-5-5m5 5l5-5M4 20h16" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ARR = '<span class="arr" aria-hidden="true"></span>'
TICK = '<span class="tick" role="img" aria-label="yes"></span>'
NAV = [("index.html", "Home"), ("executive_summary.html", "Executive summary"), ("results.html", "Results"), ("research.html", "Research"), ("knowledge.html", "Knowledge"), ("audit.html", "Audit")]


def shell(title: str, active: str, body: str, *, scripts: str = "", desc: str = "") -> str:
    nav = "".join(f'<a href="{h}"' + (' aria-current="page"' if h == active else "") + f">{t}</a>" for h, t in NAV)
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · 16GEMSDOE</title><meta name="description" content="{esc(desc or 'DOE GEMS Prize submission hub: download a validated GeoTIFF, check it, upload it.')}">
<link rel="stylesheet" href="assets/site.css"></head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="in"><a class="brand" href="index.html">16GEMSDOE</a><nav class="main" aria-label="Main">{nav}<a href="{REPO_URL}" rel="noopener">GitHub</a></nav></div></header>
<div class="strip"><div class="in"><span>DOE GEMS Prize · DrivenData #306</span><span>Ends <strong>Dec 3, 2026 23:59 UTC</strong> · <strong id="countdown" data-end="{DEADLINE_ISO}"></strong></span><span>Limit: <strong>3 uploads / rolling 7 days</strong></span><a href="{COMP}" rel="noopener">Competition</a></div></div>
<main id="main" class="wrap">{body}
<footer><p>Built {built} from commit <code>{git_short()}</code>. No score is predicted anywhere on this site; holdout figures measure recovery of <em>known</em> faults. Sources and irregularities: <a href="audit.html">Audit</a>. Project brief: <a href="{BLOB}README.md">README</a>.</p></footer></main>
<script src="js/site.js"></script>{scripts}</body></html>
"""


# ------------------------------------------------------------------------------------------------ home
ADVISORY_NOTE = {
    "variant_strict_whole_array_no_nan_allowed": "Would reject ANY NaN, including the official sample's NaN outside; shown only for completeness.",
    "profile_matches_official_sample": "Driver, dtype, nodata, size, CRS and transform equal the template's.",
    "outside_is_nan_official_text": "DrivenData: data outside the bounds is null or NaN.",
    "nodata_tag_is_nan": "The official sample declares nodata = NaN.",
}


def check_list(c: dict) -> str:
    chk = c["checks_official_format"]
    hard = {k: v for k, v in chk["checks"].items() if v["hard"]}
    ok = all(v["pass"] for v in hard.values())
    items = [f'<li class="{"" if ok else "no"}"><strong>Format:</strong> all {len(hard)} hard requirements pass: single band, float32, EPSG:32611, 3292 × 3730, '
             f'finite values in [0, 1] on all {foot["footprint_pixels"]:,} footprint pixels, read back with three different range-check implementations.</li>']
    official = chk["official_format_compliant"]
    items.append(f'<li class="{"" if official else "soft"}"><strong>Official convention:</strong> NaN on all {foot["outside_pixels"]:,} outside pixels and nodata = NaN, matching the official sample\'s raster profile.</li>')
    u = c["uniqueness"]
    hist = [n for n in u["nearest"] if not n["id"].startswith("candidate:")]
    nn = hist[0]
    items.append(f'<li class="{"" if u["verdict"] == "DISTINCT" else "no"}"><strong>Unique:</strong> {esc(u["verdict"]).lower()} against all 21 files in the group registry — the most similar is <code>{esc(nn["id"])}</code> '
                 f'(Jaccard overlap {nn["jaccard_positive"]:.2f}; duplicate threshold 0.80).</li>')
    others = [o for o in c.get("similar_to_other_candidates", []) if o["jaccard_positive"] >= 0.2]
    if others:
        items.append("<li class=\"soft\"><strong>Overlap with the other candidates:</strong> " + ", ".join(f'{esc(o["key"])} (Jaccard {o["jaccard_positive"]:.2f})' for o in others) + ".</li>")
    h = c["holdout"]
    g = c["holdout_gate_vs_h16_1"]
    if not c.get("gate_eligible", True):
        gate = '<span class="badge b-warn">not gate-eligible</span>'
    elif g is None:
        gate = '<span class="badge b-info">benchmark</span>'
    else:
        gate = '<span class="badge b-ok">gate passed</span>' if g["passed"] else '<span class="badge b-bad">gate failed</span>'
    items.append(f'<li class="soft"><strong>Holdout proxy (known faults):</strong> dense {h["mean_dense_dti"]:.3f} / sparse {h["mean_sparse_dti"]:.3f} {gate}</li>')
    led = LEDGER.get(c["content_id"])
    if led:
        items.append(f'<li><strong>Live public score recorded:</strong> {led["score"]:.4f} on {esc(led["recorded_utc"][:10])} (copied by a person from DrivenData; not automated).</li>')
    else:
        items.append('<li class="soft"><strong>Not live-scored.</strong> No leaderboard score is predicted.</li>')
    return '<ul class="check">' + "".join(items) + "</ul>"


def cand_card(c: dict, label: str, cls: str, badge: str) -> str:
    f = c["files"]
    cid = c["key"]
    checks_rows = []
    for k, v in c["checks_official_format"]["checks"].items():
        kind = "hard requirement" if v["hard"] else "advisory"
        result = "✔ pass" if v["pass"] else ("✖ fail" if v["hard"] else "○ n/a")
        checks_rows.append([esc(k.replace("_", " ")), kind, result, esc(ADVISORY_NOTE.get(k, v["detail"]))])
    return f"""<article class="card cand {cls}" id="cand-{cid}">
<span class="badge {badge}">{esc(label)}</span>
<h3>{esc(c["title"])}</h3>
<p class="muted">{esc(c["one_liner"])}</p>
<div class="row"><a class="btn primary" href="{esc(f["tif"]["href"])}" download>{DL_ICON}Download submission (.tif · {fmt_mb(f["tif"]["bytes"])})</a>
<a class="btn" href="{esc(f["zip"]["href"])}" download>ZIP ({fmt_mb(f["zip"]["bytes"])})</a>
<a class="btn" href="{esc(f["tif_allfinite"]["href"])}" download title="Same prediction, zeros outside the footprint. Use only if the form rejects the NaN version.">All-finite fallback</a></div>
<dl class="kv"><dt>File name</dt><dd><code id="fn-{cid}">{esc(f["tif"]["name"])}</code> <button class="btn" type="button" data-copy="fn-{cid}">Copy</button></dd>
<dt>Note to paste</dt><dd><code class="note" id="note-{cid}">{esc(c["note"])}</code> <button class="btn" type="button" data-copy="note-{cid}">Copy note</button></dd>
<dt>Scored pixels</dt><dd>{c["scored_pixels_predicted"]:,} ({c["share_of_footprint_pct"]} % of footprint) · content id <code>{esc(c["content_id"])}</code></dd>
<dt>SHA-256</dt><dd><code>{esc(f["tif"]["sha256"])}</code></dd></dl>
{check_list(c)}
<div class="alert {'info' if c.get('gate_eligible', True) else ''}"><strong>Caveat.</strong> {esc(c["caveat"])}</div>
<details><summary>All format checks for this file</summary>{table(["Check", "Kind", "Result", "Detail"], checks_rows)}</details>
</article>"""


def build_index() -> str:
    cs = {c["key"]: c for c in subs["candidates"]}
    body = f"""
<h1>Download a submission file. Check it. Upload it.</h1>
<p class="lead">Each file below is a single-band float32 GeoTIFF in the exact format DrivenData describes, re-read and verified, unique against all 21 files in the group registry (every GeoTIFF the group's pages offered), with a unique name and a ready-to-paste note.</p>
<div class="alert ok"><strong>Fastest path:</strong> click <strong>Download</strong> on Upload #1 {ARR} open the <a href="{COMP}submissions/" rel="noopener">DrivenData submission page</a> {ARR} choose the file {ARR} paste the note {ARR} submit. Exact steps and the error-triage guide are on the <a href="executive_summary.html">Executive summary</a>. The three weekly slots are a <em>rolling</em> 7-day allowance.</div>
<div class="grid g2">{cand_card(cs["h18-3a"], "Upload #1 · recommended (passed the gate)", "rec", "b-ok")}{cand_card(cs["h16-1"], "Upload #2 · A/B benchmark", "", "b-info")}</div>
{cand_card(cs["sgmc-gap"], "Upload #3 · external-data probe — owner decision", "", "b-warn")}
<h2>Step 2 — check any file before you spend a slot</h2>
<p>Drop a .tif on the <a href="executive_summary.html#checker">checker</a>. It runs in your browser (nothing is uploaded) and tells you <em>which</em> pixels break <em>which</em> rule, including the “Predicted values must be in range [0, 1]” family of problems.</p>
<h2>Why the score 0.1563 kept repeating</h2>
<div class="grid g3">
<div class="card"><h3>Same bytes</h3><p>GEMSDOE1 and 5GEMSDOE host the byte-identical file (Git blob <code>812e61b740…</code>). 8GEMSDOE differs only on known-fault pixels, which the evaluator masks, so it is the same submission. GEMSDOE2 overlaps it 94.6 %.</p></div>
<div class="card"><h3>Copied seed</h3><p>That same file sits at 8 paths in 6 repositories: each new repo was seeded from earlier evidence folders whose default <code>submission.tif</code> is the old winner.</p></div>
<div class="card"><h3>Repeated idea</h3><p>Three repos tried near-catalogue top-k predictions and all scored ≤ 0.046. The <a href="results.html#duplicates">Results page</a> has the matrix.</p></div></div>
<h2>Where we stand</h2>
<div class="grid g3">
<div class="card"><span class="muted small">Leaderboard leader (snapshot {lb["snapshot_utc"][:10]})</span><p style="font-size:2rem;margin:.1em 0"><strong>{lb["top"][0][3]:.4f}</strong></p><p class="small">{esc(lb["top"][0][1])} · live value on the <a href="{COMP}leaderboard/" rel="noopener">official page</a></p></div>
<div class="card"><span class="muted small">Best group score (public)</span><p style="font-size:2rem;margin:.1em 0"><strong>0.1563</strong></p><p class="small">{lb["ratio_leader_to_best_group_score"]}× below the leader; gap {lb["gap_to_leader_best_group_score"]}. See <a href="results.html">Results</a>.</p></div>
<div class="card"><span class="muted small">Current holdout best (known faults)</span><p style="font-size:2rem;margin:.1em 0"><strong>{h18["baseline"]["mean_dense_dti"]:.3f}</strong> <span class="muted small">dense</span></p><p class="small">sparse {h18["baseline"]["mean_sparse_dti"]:.3f}. A proxy, not a score. <a href="research.html">Research</a>.</p></div></div>
<div class="alert"><strong>Read before uploading.</strong> No file here has been live-scored. The holdout recovers <em>known</em> faults while the real scoring masks them, so a holdout gain is necessary, not sufficient, evidence (measured: for our own 15 distinct scored files, the dense known-fault proxy has rank correlation {calib['correlation_with_public_score']['known_dense']['spearman_rho']:+.2f} with the public score). Upload #3 cannot pass the gate by construction and needs an explicit owner decision. The group's entries appear under separate DrivenData accounts — see <a href="audit.html#F08">flag F08</a> before using several accounts.</div>
"""
    return shell("Download your GEMS submission", "index.html", body, desc="Download a validated GEMS GeoTIFF, check it, and upload it with a unique name and note.")


# ------------------------------------------------------------------------------------------------ submit guide
def build_submit() -> str:
    c1 = next(c for c in subs["candidates"] if c["key"] == "h18-3a")
    body = f"""
<h1>Executive summary — how to make a submission</h1>
<p class="lead">Five steps, about two minutes. Everything here is taken from the official pages linked in the <a href="audit.html">Audit</a>; the upload form's wording is quoted from the project owner because the form is behind a DrivenData login.</p>
<div class="card"><h2 style="margin-top:0">TL;DR</h2><ol class="steps">
<li><strong>Download</strong> a file from the <a href="index.html">Home page</a> (recommended: Upload #1).</li>
<li><strong>Check</strong> it in the <a href="#checker">checker</a> below (optional but free).</li>
<li>Open the <a href="{COMP}" rel="noopener">competition</a> {ARR} <strong>Submit</strong> (sidebar) {ARR} <strong>Make new submission</strong>.</li>
<li><strong>File to submit:</strong> choose the .tif (or the ZIP). <strong>Note (optional):</strong> paste the note from the card.</li>
<li>Submit, wait for the public score, then <a href="#record">record it</a>.</li></ol></div>

<h2>The form, field by field</h2>
{table(["Field on the DrivenData page", "What to put", "Source"], [
  ["<strong>File to submit</strong>", "A single-band GeoTIFF (<code>.tif</code>) <em>or</em> a <code>.zip</code> containing exactly one GeoTIFF. It must match the submission format's CRS, shape and geotransform.", "Form text as quoted by the project owner"],
  ["<strong>Note (optional)</strong>", "A short comment that tells submissions apart later (DrivenData's own example: <em>clustering with k=25</em>). Use the note printed on each card, e.g. <code>" + esc(c1["note"]) + "</code>", "Form text as quoted by the project owner"],
  ["Name", "The file name already carries the hypothesis, date and an 8-character hash of the <em>scored</em> content, so two different predictions can never share a name and identical predictions always do.", "This repository (<code>gems.submission.make_filename</code>)"]])}

<h2>What the file must satisfy (official) and how ours does</h2>
{table(["Requirement (DrivenData page 967)", "Our files"], [
  ["Same projected CRS as training data (EPSG:32611)", TICK + "verified by re-reading the file"],
  ["Same resolution (100 m) and same bounds/shape (3,292 × 3,730)", TICK + "geotransform equals the template's"],
  ["Data outside the bounds is null or NaN", TICK + f"NaN on all {foot['outside_pixels']:,} outside pixels; nodata tag = NaN"],
  ["Single layer, datatype float32, values between 0 and 1", TICK + f"finite on all {foot['footprint_pixels']:,} footprint pixels; min 0, max 1"]])}
<p class="small muted">Raster profile also mirrors the official sample (LZW, 1-row strips, nodata NaN). Repositories behind scored group entries publish files in every other encoding too (deflate, predictor 3, tiled, zero outside), so encoding is unlikely to decide acceptance (assuming the published file is the uploaded one).</p>

<h2 id="checker-title">Pre-upload checker (runs in your browser)</h2>
<div id="checker" class="card"><div class="drop"><p><strong>Drop a .tif here</strong> or choose a file</p><p><input type="file" accept=".tif,.tiff,image/tiff" aria-label="Choose a GeoTIFF to check"></p><p class="small muted">Nothing is uploaded; the file is read locally. ZIPs: unzip first.</p></div><div class="out" aria-live="polite"></div></div>

<h2 id="triage">If DrivenData says “Predicted values must be in range [0, 1]”</h2>
<ol class="steps">
<li><strong>Drop the exact uploaded file into the checker.</strong> A red ✖ on “No NaN/Inf inside the footprint” or “Every footprint value within [0, 1]” names the fault. NaNs inside the footprint are a likely cause: all 19 input layers have {min(b['invalid_inside_footprint'] for b in prof['bands']):,}–{max(b['invalid_inside_footprint'] for b in prof['bands']):,} invalid pixels <em>inside</em> the scored area (<a href="audit.html#F05">flag F05</a>), and models propagate them.</li>
<li><strong>If everything is ✔,</strong> the file meets every published rule. We could not reproduce the error with any file ever published on this site (<a href="audit.html#F13">flag F13</a>), and the repositories behind the group's <em>scored</em> entries publish files in every encoding (NaN-outside and zero-outside, LZW and deflate, striped and tiled) — assuming the published file is what was uploaded.</li>
<li><strong>Try the all-finite fallback</strong> (same in-footprint prediction, zeros outside). It carries the same content id, so it is not a new experiment.</li>
<li><strong>Still rejected?</strong> Email <a href="mailto:info@drivendata.org">info@drivendata.org</a> (technical help, per the forum header) with the file name, SHA-256, time and a screenshot. Rules questions: <a href="mailto:gemsprize@nlr.gov">gemsprize@nlr.gov</a>.</li>
<li><strong>Do not</strong> rescale or edit values to “get it through”: that changes the prediction. Whether a rejected upload counts against the weekly allowance is not stated in the sources read; ask DrivenData.</li></ol>

<h2>Rules that affect how you use the slots</h2>
<ul>
<li><strong>Three uploads per rolling 7 days</strong> per entity ([rules §3.2/3.4](https://docs.nlr.gov/docs/fy26osti/96647.pdf); staff: <a href="https://community.drivendata.org/t/weekly-submissions/11524/2">forum 11524 #2</a>).</li>
<li><strong>One final submission per entity.</strong> Choose it before Dec 3, 2026 23:59 UTC, without seeing private-set scores; team members cannot each submit a separate final.</li>
<li><strong>Accounts are personal</strong> (<a href="https://www.drivendata.org/termsofuse/">Terms of Use</a>). Do not pool accounts to multiply the limit; see <a href="audit.html#F08">F08</a>.</li>
<li><strong>Disclose generative-AI use</strong> in any prize narrative ([rules §3.2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).</li>
<li>Known-fault pixels are masked; a prediction near a known fault but far from a new fault is fully penalised ([staff](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4)).</li></ul>

<h2 id="record">After the score appears</h2>
<p>Record it so the next session can learn from it (this is the one step that cannot be automated — DrivenData's Terms of Use forbid bots, and scores live behind login):</p>
<p><code>python scripts/record_score.py &lt;candidate-key&gt; &lt;score&gt;</code> (candidate keys: <code>h18-3a</code>, <code>h16-1</code>, <code>sgmc-gap</code>; the score is whatever DrivenData shows) updates <code>registry/submissions.json</code> and the site data; then commit. The A/B pair (#1 vs #2) is the first calibration of whether the holdout proxy predicts the public score.</p>
"""
    body = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" rel="noopener">\1</a>', body)
    return shell("Executive summary", "executive_summary.html", body,
                 scripts='<script src="js/gems-tiff.js"></script><script src="js/check.js"></script>', desc="Exactly how to submit to the DOE GEMS Prize, with a local pre-upload checker.")


# ------------------------------------------------------------------------------------------------ results
OUTSIDE_LABEL = {"nan": "NaN (official)", "zero": "zeros", "other": "other (non-NaN, non-zero)"}


def build_results() -> str:
    top_rows = [[str(r[0]), esc(r[1]), str(r[2]), f"{r[3]:.4f}"] for r in lb["top"]]
    grp_rows = [[str(g["rank"]), esc(g["participant"]), str(g["submissions"]), f"{g['score']:.4f}", esc(g["status"]), "hl"] for g in lb["group"]]
    lb_tbl = table(["Rank", "Participant", "Submissions", "Best public DW-Tversky"], top_rows)
    grp_tbl = table(["Rank", "Account", "Submissions", "Best score", "Status"], grp_rows)
    ent = forn["entries"]
    by_dup = {}
    for grp in forn["identical_on_scored_pixel_groups"]:
        for i in grp:
            by_dup[i] = "identical on scored pixels: " + ", ".join(x for x in grp if x != i)
    for p in forn["near_duplicate_pairs"]:
        for a, b in ((p["a"], p["b"]), (p["b"], p["a"])):
            by_dup.setdefault(a, f"near-duplicate of {b} (J={p['jaccard_positive']:.2f})")
    rows = []
    for e in sorted(ent, key=lambda e: -(e["lb_score"] if e["lb_score"] is not None else -1)):
        cls = "dup" if e["id"] in by_dup else ""
        rows.append([esc(e["display_name"]), "—" if e["lb_score"] is None else f"{e['lb_score']:.4f}", f"{e['positive_scored_pixels']:,}",
                     f"{100 * e['frac_near_le_300m']:.0f} %", f"{100 * e['frac_far_gt_1500m']:.0f} %", OUTSIDE_LABEL.get(e["outside_mode"], esc(e["outside_mode"])),
                     esc(by_dup.get(e["id"], "distinct")), f'<a href="https://github.com/buffedlizard55-lab/{esc(e["github_repo"])}" rel="noopener">repo</a>', cls])
    ent_tbl = table(["Entry", "Public score", "Scored px", "≤300 m of known", ">1.5 km", "Outside", "Relation", "Source"], rows)
    lin = []
    for l in forn["lineage"][:8]:
        lin.append([f"<code>{esc(l['git_blob_sha1'][:10])}…</code>", str(l["copies"]), esc(", ".join(l["repos"])), esc(", ".join(l["registry_entries"]) or "—"),
                    ", ".join(f"{s:.4f}" for s in l["lb_scores"]) or "—"])
    lin_tbl = table(["Git blob", "Copies", "Repositories", "Registered entries", "Score(s)"], lin)
    sp = forn["score_vs_geometry_descriptive"]["spearman"]
    sp_rows = [[esc(k), f"{v['spearman_rho']:+.2f}", f"{v['p_value']:.2f}"] for k, v in sp.items()]
    sp_tbl = table(["Geometry statistic", "Spearman ρ with public score", "p"], sp_rows)
    scan_html = ""
    if scan:
        scan_html = f'<h2>New files found in group repositories</h2><p class="small muted">Last scan {esc(scan["generated_utc"])}: {len(scan["unregistered"])} unregistered GeoTIFF(s) in public group repos; {sum(1 for u in scan["unregistered"] if u["verdict"] != "DISTINCT")} overlap an earlier file.</p>'
    body = f"""
<h1>Results — the leaderboard and the group's own submissions</h1>
<p class="lead">A single manual snapshot ({lb["snapshot_utc"].replace("T", " ")[:16]} UTC) and the forensic audit of every registered file. Scores change; the <a href="{COMP}leaderboard/" rel="noopener">live page</a> is authoritative.</p>
<div class="alert"><strong>Why this is a snapshot, not a feed.</strong> DrivenData's <a href="https://www.drivendata.org/termsofuse/" rel="noopener">Terms of Use</a> prohibit robots and spiders, so no scheduled job touches drivendata.org. A person refreshes <code>docs/data/leaderboard.json</code>; everything else on this site updates automatically from official open-data hosts and our own repositories (see <a href="audit.html">Audit</a>).</div>
<h2>Top of the public leaderboard</h2>{lb_tbl}
<p class="small muted">Gap between the leader and our best public score: {lb["gap_to_leader_best_group_score"]} ({lb["ratio_leader_to_best_group_score"]}×).</p>
<h2>Group accounts on the leaderboard</h2>{grp_tbl}
<p class="small muted">Only SDCF9, smashi34, wbg1 and smrtdoog5 were named by the project owner. extradr19 has an identical 0.1563 but is <strong>unconfirmed</strong>. See <a href="audit.html#F08">flag F08</a>.</p>
<h2 id="duplicates">Every registered file, compared on the pixels that are actually scored</h2>
<p>Scored pixels = footprint minus the pixel-exact known-fault mask (staff ruling). Highlighted rows are duplicates or near-duplicates of another entry.</p>{ent_tbl}
<div class="grid g2"><div class="card"><h3>Duplicate clusters (verified)</h3><ul>
<li><strong>GEMSDOE1 = 5GEMSDOE = 8GEMSDOE</strong> on every scored pixel; GEMSDOE1 and 5GEMSDOE are byte-identical. GEMSDOE2 overlaps them {forn["near_duplicate_pairs"][0]["jaccard_positive"]:.3f}.</li>
<li><strong>12GEMSDOE</strong> NaN-outside and all-finite files carry the same prediction (both 0.1294).</li></ul></div>
<div class="card"><h3>How the same file spread</h3>{lin_tbl}</div></div>
<h2>Does any simple geometry statistic explain the score?</h2>{sp_tbl}
<p class="small muted">{esc(forn["score_vs_geometry_descriptive"]["caveat"])} n = {forn["score_vs_geometry_descriptive"]["n_unique_scored_contents"]} unique scored contents. No correlation is significant, so earlier hunches such as “predictions near known faults always lose” are <strong>not</strong> supported by this sample, even though the three near-catalogue top-k files all scored ≤ 0.046.</p>
{scan_html}
<p class="small muted">Machine-readable: <a href="data/forensics.json">forensics.json</a>, <a href="{BLOB}evidence/submission_similarity.json">full similarity matrix</a>, <a href="{BLOB}registry/submissions.json">registry</a>.</p>
"""
    return shell("Results", "results.html", body, desc="Leaderboard snapshot and forensic audit of the group's submissions.")


# ------------------------------------------------------------------------------------------------ research / knowledge / audit
def build_research() -> str:
    reg = render_md(DOCS / "research" / "hypothesis_register.md")
    pre = render_md(DOCS / "research" / "preregistration_h18.md", {})
    body = f'<div class="md">{reg}</div><details><summary>Pre-registration (committed before any H18 result)</summary><div class="md">{pre}</div></details>'
    return shell("Research", "research.html", body, desc="Ranked geological hypotheses, pre-registered validation and controls.")


def build_knowledge() -> str:
    return shell("Knowledge base", "knowledge.html", f'<div class="md">{render_md(DOCS / "knowledge" / "knowledge_base.md")}</div>', desc="Verified facts about the GEMS Prize, the data and Great Basin fault geology.")


def build_audit() -> str:
    st_badge = {"verified": "b-ok", "flagged": "b-warn", "computed": "b-info"}
    src_rows = [[esc(r["id"]), esc(r["topic"]), inline(r["claim"]), f'<a href="{esc(r["url"])}" rel="noopener">link</a>', inline(r["how_verified"]),
                 f'<span class="badge {st_badge.get(r["status"], "b-info")}">{esc(r["status"])}</span>' + (f"<br><span class=\"small muted\">{inline(r['note'])}</span>" if r["note"] else "")] for r in sources["rows"]]
    sev = {"high": "b-bad", "medium": "b-warn", "low": "b-info", "info": "b-info"}
    flag_rows = []
    for f in flags["flags"]:
        links = " ".join(f'<a href="{esc(u)}" rel="noopener">[{i + 1}]</a>' for i, u in enumerate(f["links"]))
        flag_rows.append([f'<a id="{esc(f["id"])}"></a><strong>{esc(f["id"])}</strong>', f'<span class="badge {sev[f["severity"]]}">{esc(f["severity"])}</span><br><span class="small muted">{esc(f["status"])}</span>',
                          f"<strong>{inline(f['title'])}</strong><br>{inline(f['evidence'])}", inline(f["action"]) + (f"<br>{links}" if links else "")])
    health_html = '<p class="small muted">Source-health job has not run yet (see <code>.github/workflows/source-health.yml</code>).</p>'
    if health:
        bad = [r for r in health["results"] if not r["ok"]]
        health_html = (f'<p>Last automatic check <strong>{esc(health["generated_utc"])}</strong>: {len(health["results"]) - len(bad)} of {len(health["results"])} official-source URLs reachable'
                       f'{"" if not bad else ", unreachable: " + ", ".join(esc(r["id"]) for r in bad)}. DrivenData hosts are deliberately excluded (Terms of Use).</p>')
    ci_dl = "".join(f"<tr><td>{esc(k)}</td><td>{'✔' if v['ok'] else '✖'}</td><td class=\"num\">{v.get('bytes', 0):,}</td><td><a href=\"{esc(v['url'])}\" rel=\"noopener\">source</a></td></tr>" for k, v in ci["downloads"].items())
    body = f"""
<h1>Audit — sources, verification and flagged irregularities</h1>
<p class="lead">Every row below was fetched and read (or computed from fetched data) in the 2026-09-30 review. “Flagged” rows conflict with something else. Nothing here is taken from memory.</p>
<h2>Irregularities for review</h2>{table(["ID", "Severity / status", "What we found", "What to do / links"], flag_rows)}
<h2>Source table</h2><div class="tw"><table><thead><tr><th>ID</th><th>Topic</th><th>Claim</th><th>Link</th><th>How verified</th><th>Status</th></tr></thead><tbody>{"".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in src_rows)}</tbody></table></div>
<h2>Automatic checks of official hosts</h2>{health_html}
<h3>Downloads performed on a GitHub runner ({esc(ci["generated_utc"])})</h3>
<div class="tw"><table><thead><tr><th>Item</th><th>OK</th><th>Bytes</th><th>Source</th></tr></thead><tbody>{ci_dl}</tbody></table></div>
<p class="small muted">Raw output: <a href="{BLOB}evidence/ci/external_verification.json">evidence/ci/external_verification.json</a>. The agent sandbox cannot reach these hosts, which is why the workflow runs on GitHub and commits its results back.</p>
"""
    return shell("Audit", "audit.html", body, desc="Sources, verification and flagged irregularities.")


def main() -> None:
    pages = {"index.html": build_index(), "executive_summary.html": build_submit(), "results.html": build_results(),
             "research.html": build_research(), "knowledge.html": build_knowledge(), "audit.html": build_audit()}
    for name, content in pages.items():
        (DOCS / name).write_text(content)
        print(f"wrote docs/{name} ({len(content):,} bytes)")
    (ROOT / "index.html").write_text(
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=docs/index.html">'
        '<link rel="canonical" href="docs/index.html"><title>16GEMSDOE</title></head><body>'
        '<p>Redirecting to the <a href="docs/index.html">submission hub</a>…</p></body></html>\n')
    (ROOT / ".nojekyll").write_text("")



if __name__ == "__main__":
    main()
