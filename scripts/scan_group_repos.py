"""Scan the group's public GEMS repositories for NEW GeoTIFFs and compare each against everything already uploaded.

Answers "are we about to submit the same thing again?" automatically: any published .tif that is not in
registry/submissions.json is fetched (via the authenticated ``gh`` CLI), format-checked, and compared on the scored pixels
(footprint minus known-fault mask) with every registered file.  Output: docs/data/group_scan.json.
Needs only the footprint payload in docs/data and two small public files (labels + registered submissions).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import rasterio
from rasterio.io import MemoryFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import forensics as F  # noqa: E402
from gems.footprint import load_footprint, write_template  # noqa: E402
from gems.paths import GROUP_DIR, SITE_DATA_DIR  # noqa: E402
from gems.submission import check_variants  # noqa: E402

OWNER = "buffedlizard55-lab"
REPO_RE = re.compile(r"^(\d+)?GEMSDOE\d*$")
IGNORE = ("/bridge/", "fixture", "labels.tif", "sample_submission", "example_submission", "existing_faults", "proxy_", "qfaults_catalogue",
          "/external/", "/derived/", "/cache/", "/dem/", "geodawn_", "prior_u8", "/evidence/runs/", "/evidence/baseline", "/evidence/proxy", "/evidence/xcat")
LABELS_SHA256 = "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093"
MAX_BYTES = 8_000_000
MAX_FILES = 60


def gh_json(path: str):
    return json.loads(subprocess.run(["gh", "api", path, "--paginate"], check=True, capture_output=True).stdout or "[]")


# --- GitHub access layer (module-level so tests can substitute an offline fake) ----------------------------------------
def list_repos(owner: str) -> list[str]:
    return [r["name"] for r in gh_json(f"users/{owner}/repos?per_page=100") if REPO_RE.match(r["name"])]


def list_tree(owner: str, repo: str) -> list[dict]:
    try:
        tree = json.loads(subprocess.run(["gh", "api", f"repos/{owner}/{repo}/git/trees/main?recursive=1"], check=True, capture_output=True).stdout)
    except subprocess.CalledProcessError:
        return []
    return tree.get("tree", [])


def fetch_file(owner: str, repo: str, path: str, dest: Path) -> bytes:
    return F.gh_fetch_raw(owner, repo, path, dest)


def main() -> int:
    reg = json.loads((ROOT / "registry" / "submissions.json").read_text())["entries"]
    reg_blobs = {e["git_blob_sha1"] for e in reg}
    fp = load_footprint()
    labels_path = GROUP_DIR / "_labels.tif"
    data = fetch_file(OWNER, "GEMSDOE", "data/bridge/existing_faults.tif", labels_path)
    if F.sha256_bytes(data) != LABELS_SHA256:
        print("labels file hash mismatch; aborting")
        return 1
    with rasterio.open(labels_path) as s:
        lab = s.read(1)
    grid = F.Grid.from_footprint(fp, lab)
    template = write_template(Path(tempfile.mkdtemp()) / "template.tif")
    history = []
    for e in reg:
        dest = GROUP_DIR / f"{e['id']}.tif"
        if not dest.exists() or F.git_blob_sha1(dest.read_bytes()) != e["git_blob_sha1"]:
            fetch_file(OWNER, e["github_repo"], e["repo_path"], dest)
        with rasterio.open(dest) as s:
            history.append({"id": e["id"], "array": s.read(1), "lb_score": e["lb_score"]})

    repos = list_repos(OWNER)
    seen_blobs, found = set(), []
    tifs_seen = 0
    for repo in sorted(repos):
        for ent in list_tree(OWNER, repo):
            path = ent["path"]
            if ent["type"] != "blob" or not path.lower().endswith((".tif", ".tiff")):
                continue
            tifs_seen += 1
            if any(tok in path for tok in IGNORE) or ent["sha"] in reg_blobs or ent["sha"] in seen_blobs:
                continue
            if not (path.startswith(("docs/", "downloads/")) or "/downloads/" in path):
                continue
            if (ent.get("size") or 0) > MAX_BYTES:
                continue
            seen_blobs.add(ent["sha"])
            found.append((repo, path, ent["sha"], ent.get("size")))
    found = found[:MAX_FILES]
    unreg = []
    for repo, path, sha, size in found:
        dest = GROUP_DIR / "scan" / f"{repo}__{path.replace('/', '__')}"
        try:
            blob = fetch_file(OWNER, repo, path, dest)
            with MemoryFile(blob) as m, m.open() as s:
                arr = s.read(1)
                ok_shape = arr.shape == fp.shape
            if not ok_shape:
                unreg.append({"repo": repo, "path": path, "bytes": size, "git_blob_sha1": sha, "verdict": "NOT_A_SUBMISSION_GRID"})
                continue
            chk = check_variants(dest, template)
            gate = F.gate_candidate(arr, grid, history)
            nn = gate["nearest"][0] if gate["nearest"] else None
            unreg.append({"repo": repo, "path": path, "bytes": size, "git_blob_sha1": sha, "format_ok": chk["ok_to_upload"],
                          "hard_failures": chk["hard_failures"], "verdict": gate["verdict"],
                          "nearest_id": nn["id"] if nn else None, "nearest_jaccard": nn["jaccard_positive"] if nn else None,
                          "nearest_lb_score": nn["lb_score"] if nn else None, "scored_positive_pixels": gate["candidate_positive_scored_pixels"]})
        except Exception as exc:  # noqa: BLE001
            unreg.append({"repo": repo, "path": path, "bytes": size, "git_blob_sha1": sha, "verdict": "ERROR", "error": repr(exc)[:160]})
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "repos_scanned": len(repos), "tif_blobs_seen": tifs_seen,
           "registered_entries": len(reg), "unregistered": unreg,
           "note": "Only published downloads are scanned (docs/, downloads/). A DISTINCT verdict means Jaccard < 0.80 with every registered file on scored pixels."}
    (SITE_DATA_DIR / "group_scan.json").write_text(json.dumps(out, indent=2) + "\n")
    dups = [u for u in unreg if u["verdict"] in ("DUPLICATE", "NEAR_DUPLICATE")]
    print(f"repos={len(repos)} tif blobs={tifs_seen} unregistered scanned={len(unreg)} duplicates/near={len(dups)}")
    for u in unreg[:12]:
        print(" ", u["repo"], u["path"][-50:], u["verdict"], u.get("nearest_id"), u.get("nearest_jaccard"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
