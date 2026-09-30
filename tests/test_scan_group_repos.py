"""End-to-end test of scripts/scan_group_repos.py against an OFFLINE fake GitHub (no network, no `gh`)."""
from __future__ import annotations

import hashlib
import importlib.util
import json

import numpy as np
import rasterio

from gems.paths import ROOT
from gems.submission import write_submission

spec = importlib.util.spec_from_file_location("scan_group_repos", ROOT / "scripts" / "scan_group_repos.py")
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def _pred(footprint, seed):
    rng = np.random.default_rng(seed)
    a = np.where(footprint, (rng.random(footprint.shape) < 0.02), False).astype(np.float32)
    a[~footprint] = np.nan
    return a


def test_scan_flags_duplicates_ignores_noise_and_writes_report(tmp_path, monkeypatch, footprint, template_tif):
    reg_dir = tmp_path / "root" / "registry"
    reg_dir.mkdir(parents=True)
    entries = [{"id": f"R{i}", "github_repo": "1GEMSDOE", "repo_path": f"docs/downloads/r{i}.tif", "git_blob_sha1": f"{i:040x}", "lb_score": 0.1 * i} for i in (1, 2, 3)]
    (reg_dir / "submissions.json").write_text(json.dumps({"entries": entries}))

    files: dict[tuple[str, str], bytes] = {}
    for i, e in enumerate(entries):                                             # registered files
        p = write_submission(_pred(footprint, 100 + i), template_tif, tmp_path / f"r{i}.tif")
        files[(e["github_repo"], e["repo_path"])] = p.read_bytes()
    dup = write_submission(_pred(footprint, 100), template_tif, tmp_path / "dup.tif", outside="zero")   # same scored pixels as R1 (first entry), zero-outside container
    new = write_submission(_pred(footprint, 999), template_tif, tmp_path / "new.tif")
    files[("77GEMSDOE", "docs/downloads/copy_of_r1.tif")] = dup.read_bytes()
    files[("77GEMSDOE", "docs/downloads/brand_new.tif")] = new.read_bytes()
    files[("77GEMSDOE", "docs/downloads/labels.tif")] = b"ignored"
    files[("77GEMSDOE", "data/bridge/existing_faults.tif")] = b"ignored"

    lab = np.zeros(footprint.shape, dtype=np.int8)
    lab[1500:1503, 800:1600] = 1
    lab_path = tmp_path / "lab.tif"
    with rasterio.open(template_tif) as t:
        prof = t.profile.copy()
    prof.update(dtype="int8", nodata=-1)
    with rasterio.open(lab_path, "w", **prof) as d:
        d.write(np.where(footprint, lab, -1).astype(np.int8), 1)
    files[("GEMSDOE", "data/bridge/existing_faults.tif")] = lab_path.read_bytes()

    def fake_fetch(owner, repo, path, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(files[(repo, path)])
        return files[(repo, path)]

    def fake_tree(owner, repo):
        return [{"type": "blob", "path": p, "sha": hashlib.sha1(p.encode()).hexdigest(), "size": len(b)} for (r, p), b in files.items() if r == repo]

    monkeypatch.setattr(scan, "ROOT", tmp_path / "root")
    monkeypatch.setattr(scan, "GROUP_DIR", tmp_path / "group")
    monkeypatch.setattr(scan, "SITE_DATA_DIR", tmp_path / "out")
    monkeypatch.setattr(scan, "LABELS_SHA256", hashlib.sha256(lab_path.read_bytes()).hexdigest())
    monkeypatch.setattr(scan, "list_repos", lambda owner: ["77GEMSDOE"])
    monkeypatch.setattr(scan, "list_tree", fake_tree)
    monkeypatch.setattr(scan, "fetch_file", fake_fetch)
    (tmp_path / "out").mkdir()

    assert scan.main() == 0
    out = json.loads((tmp_path / "out" / "group_scan.json").read_text())
    by_path = {u["path"]: u for u in out["unregistered"]}
    assert set(by_path) == {"docs/downloads/copy_of_r1.tif", "docs/downloads/brand_new.tif"}        # labels.tif and bridge/ ignored
    assert by_path["docs/downloads/copy_of_r1.tif"]["verdict"] == "DUPLICATE"
    assert by_path["docs/downloads/copy_of_r1.tif"]["nearest_id"] == "R1"
    assert by_path["docs/downloads/brand_new.tif"]["verdict"] == "DISTINCT"
    assert all(u["format_ok"] for u in by_path.values())


def test_scan_aborts_when_the_labels_file_hash_is_wrong(tmp_path, monkeypatch):
    (tmp_path / "root" / "registry").mkdir(parents=True)
    (tmp_path / "root" / "registry" / "submissions.json").write_text(json.dumps({"entries": []}))
    monkeypatch.setattr(scan, "ROOT", tmp_path / "root")
    monkeypatch.setattr(scan, "GROUP_DIR", tmp_path / "group")
    monkeypatch.setattr(scan, "fetch_file", lambda o, r, p, d: (d.parent.mkdir(parents=True, exist_ok=True), d.write_bytes(b"not the labels"), b"not the labels")[2])
    assert scan.main() == 1
