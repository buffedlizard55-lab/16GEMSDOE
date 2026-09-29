# 16GEMSDOE — DOE GEMS research & submission hub

**Start here each session.** Read this README before proposing or changing an experiment. It is the standing project brief: maximize the probability of a real competition win, own the outcome, verify evidence, learn from failure, and do not spend a submission slot on an unvalidated idea.

- **GitHub Pages site:** [`docs/index.html`](docs/index.html)
- **Executive summary / submission walkthrough:** [`docs/executive_summary.html`](docs/executive_summary.html)
- **New geological hypothesis register:** [`docs/research/hypothesis_register.md`](docs/research/hypothesis_register.md)
- **Live DrivenData leaderboard:** [Competition leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
- **Cached leaderboard and audit JSON:** [`docs/leaderboard.json`](docs/leaderboard.json)

> **Current decision:** Do not treat the existing 16GEMSDOE GeoTIFFs as proven leaderboard improvements. They pass local format validation, but have no reported live competition score. The new H17-1 candidate failed our spatial-holdout promotion gate, so it is not a submission candidate. No DrivenData submission slot has been used in this review.

---

## Standing project brief — read at the start of every session

### Mission
Develop, test, and document scientifically defensible predictions of faults associated with geothermal systems in the GeoDAWN region. The competition’s labels are incomplete; the official challenge describes a private set of expert-mapped faults and a later expert review of submissions. Our goal is to compete for the top of the leaderboard and contribute credible candidate structures—not to claim that a high score or a model prediction proves a geological discovery.

### Arena values in practice
- **Maximize P(Win):** Prioritize the highest-leverage experiments, weigh score potential against false-positive risk, and use a validation gate before consuming a submission opportunity.
- **Own the Outcome:** Reproduce results, repair broken pipeline steps, report failed hypotheses, keep data provenance and assumptions visible, and leave a useful next step.

### Required research and submission gate
Before implementing a new strategy:
1. Propose and rank **3–5 genuinely different geological hypotheses**. For each, name the exact input layers, physical signal/transform, reason it could find a fault missing from the public catalogue, difference from prior experiments, data source/availability, expected gain, and implementation cost.
2. Use official, trusted sources and link them. Separate **observed facts**, **computed results**, and **inferences**. If the available sources do not support a claim, label it uncertain or omit it.
3. Validate the top candidate on the repository’s spatially blocked holdout, compared with the current holdout best. Do not use held-out labels to tune thresholds. A local pass is not evidence that hidden leaderboard DTI will improve.
4. Do not recommend or make a weekly submission from a new hypothesis unless it beats the agreed holdout gate. Never spend a slot on a duplicate or on a candidate that has not been validated.
5. Before upload, validate the GeoTIFF against the official template: single-band float32, same CRS/grid/transform/bounds, and predictions in `[0,1]` throughout the evaluation footprint. Give each genuinely different prediction a unique filename and a short, truthful DrivenData note. Outside-footprint encoding twins are not scientifically unique submissions.

### Core source
The [official DrivenData problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) defines the target, distance-weighted Tversky metric, 300 m support, input data and submission format. The [USGS GeoDAWN release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) describes its regional magnetic/radiometric data and related lidar collection. A longer source-linked hypothesis plan and research caveats are in [`docs/research/hypothesis_register.md`](docs/research/hypothesis_register.md).

---

## What we learned about repeated 0.1563 scores

### Verified duplicate: GEMSDOE1 and 5GEMSDOE
The public GitHub repositories both contain `data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif`. Their Git blob IDs match (`812e61b74050d1350cc2bde1fab0c76ead32e0c4`), and independently hashing the retrieved file content gives the same SHA-256 for both:

```text
7f00890a62878d612fb5eef67a9a364a2df819433dde74b6762ce4fc0fc4fe15
```

Each file is 570,890 bytes. The matching reported score is therefore explained: those two entries are the **same uploaded prediction**, not two distinct methods independently achieving 0.1563.

### 8GEMSDOE: different file, same effective off-catalogue predictions
A pixelwise check of `8GEMSDOE_Hedge-v2_submission.tif` finds it equals `max(ens12, catalogue)`: all differences from `ens12` occur on the existing catalogue mask, and the off-catalogue prediction mask is identical. Its reported score is also 0.1563. This is **consistent** with catalogue pixels being neutral in scoring, but a public score rounded to four decimals is not proof of the evaluator’s implementation; the official metric description does not state that rule. Do not present that inference as a confirmed competition rule.

The `12GEMSDOE` pair is another important duplication: the NaN-outside and zero-outside variants have identical in-footprint predictions. They are different containers/encodings, not distinct scientific submissions. Likewise, this repo’s `a16f01` and `b16f02` files have identical in-footprint predictions; do not submit both.

### Current leaderboard snapshot
The request cited 0.3049 as the current top score. When checked on **2026-09-29 at approximately 23:45 UTC**, the public [DrivenData leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) showed rank 1 at **0.3168**. Leaderboard values can change; open the live source before acting. This cached snapshot is not a continuously refreshed API feed.

The source-linked forensic record is [`evidence/group_forensic_audit.json`](evidence/group_forensic_audit.json). Its historical scores are the values recorded in the group’s submissions/pages and should be treated as time-stamped observations, not predictions of current private-set performance.

---

## Current spatial validation decision

The four-quadrant holdout was rerun from the locally prepared files using `scripts/run_spatial_holdout_and_build.py`. Its current best is H16-1 at mean **0.21272 dense / 0.08541 sparse-proxy DTI**. These scores measure transfer to held-out portions of the **known** fault catalogue plus a synthetic sparse-component proxy; they are not hidden leaderboard scores.

We preregistered H17-1, a cross-sensor magnetic–gravity edge-agreement experiment, as the top new candidate and validated it using the same folds, sampling, classifier family, ridge ranking and prediction budget. It scored **0.15759 dense / 0.06227 sparse-proxy DTI**, versus **0.21272 / 0.08541** for H16-1, and lost in every fold. It **failed** the promotion gate. The report includes per-fold scores, data hashes and method: [`evidence/hypothesis_h17_1_validation.json`](evidence/hypothesis_h17_1_validation.json). No H17-1 GeoTIFF was generated and no submission slot was spent.

The complete ranked list—including hypotheses not yet tested, implementation costs, official sources, and the validation protocol—is [`docs/research/hypothesis_register.md`](docs/research/hypothesis_register.md).

---

## Downloadable prediction artifacts and submission instructions

The existing files under [`docs/downloads/`](docs/downloads/) are **format-validated experimental artifacts**. Format validation only confirms the local GeoTIFF requirements; it does not establish that the file beats the 0.1563 historical score, the current leader, or the H16-1 holdout result. None is reported as live-scored. See the site’s [executive summary](docs/executive_summary.html) before upload.

1. Open the site and select **one genuinely distinct** `.tif` (or the `.zip` containing the single-band TIFF).
2. Copy the short experiment note shown beside that file. The name/comment should describe the contents and not imply a score that has not been measured.
3. On the [DrivenData submission page](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/), select the file and paste the note. Check the current competition rules/account page for any submission-rate limit; this repository has not independently verified a rolling-limit rule.
4. Before uploading, confirm the downloaded file hash/validation report and confirm it is not equivalent in-footprint to a prior upload. Do not upload `a16f01` and `b16f02` as separate experiments: they differ only outside the evaluation footprint.

The official format requires EPSG:32611, 100 m pixels, matching bounds/grid, single-band float32 and probabilities/confidence in `[0,1]`; outside the bounds are null/NaN. The local validator is [`src/gems/validator.py`](src/gems/validator.py). The exact reason for a prior rejected file cannot be established without that rejected raster: feature NaNs can propagate, but out-of-range values or another format issue are also possible.

---

## Data placement, reproducibility, and tests

Raw and derived rasters are ignored by Git. The downloader retrieves team-bridged competition files and public USGS-derived files, then verifies pinned SHA-256 values. The bridge hash establishes consistency with the team artifact, **not independent provenance from the login-gated DrivenData download**. Data preparation writes `evidence/data_verification.json` with actual file hashes, sizes, grid metadata and measured irregularities.

```bash
# Download/place the competition and public auxiliary rasters
bash scripts/download_competition_data.sh

# Create the virtual environment and dependencies if needed
python3 -m venv .venv
.venv/bin/python -m pip install numpy rasterio scipy scikit-learn pytest

# Verify input files and prepare evidence
.venv/bin/python scripts/prepare_data.py

# Recompute the four-quadrant spatial holdout (CPU-capable; several minutes)
.venv/bin/python scripts/run_spatial_holdout_and_build.py

# Validate the preregistered H17-1 idea only; creates evidence JSON, not a submission TIFF
.venv/bin/python scripts/validate_h17_1.py

# Run tests
.venv/bin/python -m pytest -q
```

The download script and training/holdout code use public team GitHub files as a bridge because the DrivenData data tab requires login. Do not commit the downloaded multi-gigabyte DEM data or derived caches. Check [`evidence/data_verification.json`](evidence/data_verification.json) for file hashes and [`evidence/dem10_fetch_verification.json`](evidence/dem10_fetch_verification.json) for 10 m DEM provenance.

---

## Verified sources and limitations

- [DrivenData challenge description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) — objective, known incompleteness, metric and submission format.
- [Live leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) — open for current scores; repository snapshot has a timestamp.
- [USGS GeoDAWN data release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and), [USGS catalog record](https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7), correct GeoDAWN DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ).
- [USGS 3DEP program](https://www.usgs.gov/3d-elevation-program) and [official elevation ImageServer](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer).
- [USGS publication on fault-controlled geothermal systems in northern Nevada](https://www.usgs.gov/publications/geothermal-systems-northern-nevada).
- [USGS three-dimensional geological mapping and geothermal potential](https://pubs.usgs.gov/publication/70202167).
- The [official competition dataset page](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) is login-gated here. The local `sample_submission.tif` has 60,988 positive pixels and an identical positive mask to the local `labels.tif`; this conflicts with the official problem page’s description of an all-absence sample template. This is a **verified property of the locally bridged files**, not independently verified provenance of the original private download. It remains unresolved.
- A previously cited lidar ScienceBase item URL returned “Not Found” during review, and the prior `10.5066/P9Z6SA1Z` GeoDAWN DOI citation was incorrect. The current source register flags these; do not reuse those citations as verified sources.
- No holdout design can recreate the private test geography/labels. A better local score is evidence for further testing, not a guarantee of a higher public or final prize score.
