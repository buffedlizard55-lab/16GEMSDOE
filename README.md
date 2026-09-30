# 16GEMSDOE — DOE GEMS Prize research & submission hub

> **Start here every session.** Read this file, then the *Original request* at the bottom (verbatim), then run `python -m pytest -q` (optional real-browser test: `tests/browser/e2e_checker.mjs`). Do not propose or change an experiment before doing so. `AGENTS.md` repeats this for automated agents.

| | |
|---|---|
| **Site (GitHub Pages)** | <https://buffedlizard55-lab.github.io/16GEMSDOE/> → [`docs/index.html`](docs/index.html) — download-first home page |
| **Executive summary: how to submit** | [`docs/executive_summary.html`](docs/executive_summary.html) (includes a local pre-upload checker) |
| Results / Research / Knowledge / Audit | [`results`](docs/results.html) · [`research`](docs/research.html) · [`knowledge`](docs/knowledge.html) · [`audit`](docs/audit.html) |
| Competition | [DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/) — ends **Dec 3, 2026 23:59 UTC** · [leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) |
| Official rules | [NLR rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) — three uploads per **rolling** week; one final submission per entity |

## Status (2026-09-30)

* **Submission files exist and are obvious.** Three candidates are on the home page, each a single-band float32 GeoTIFF in the official format (NaN outside the footprint, finite 0–1 inside), with a ZIP, an all-finite fallback, a unique hash-based file name and a ready-to-paste note. All are verified by re-reading them three ways, by a Node-run browser checker, and by the uniqueness gate against **all 21** files in the group registry (every GeoTIFF the group's pages offered).
* **GitHub Actions status:** `external-verification` ran on GitHub and its results are committed in `evidence/ci/`. `ci` runs on every pull request and on pushes to `main`. `source-health` (weekly) and `group-scan` (daily) run on a schedule from `main`; trigger each once from the Actions tab to confirm it on the real runner (the scanner has only been tested against an offline fake).
* **No file is live-scored and no score is predicted.** Upload #1 (H18-3a) passed the pre-registered holdout gate; #2 (H16-1) is the benchmark for an A/B; #3 (USGS geologic-map faults) cannot pass the gate by construction and needs an owner decision.
* **Why 0.1563 repeated (verified):** GEMSDOE1 and 5GEMSDOE host the byte-identical file; 8GEMSDOE differs only on masked known-fault pixels; GEMSDOE2 overlaps 94.6 %. That file sits at 8 paths in 6 repos. See [Results](docs/results.html).
* **The holdout is a weak gate (measured).** Across the group's 15 distinct scored files, the dense known-fault proxy has Spearman ρ = +0.17 (p = 0.54) with the public score; the USGS-geologic-map-gap truth gives ρ = +0.52 (p = 0.048). Treat every holdout figure as weak evidence; the first live A/B recalibrates it ([`evidence/proxy_calibration_vs_lb.json`](evidence/proxy_calibration_vs_lb.json)).
* **The "[0, 1]" upload error could not be reproduced** with any file ever published here; a triage path and checker are provided ([flag F13](docs/audit.html#F13)).
* **Leaderboard leader 0.3168** (snapshot 2026-09-30; your 0.3049 was stale). Our best public score is 0.1563 (2.03× lower).

## Requirements → evidence (traceability)

| # | Request | Status | Evidence |
|---|---|---|---|
| 1 | Easy-to-download submission TIF, obvious at the top of the site | ✅ | [`docs/index.html`](docs/index.html); files in [`docs/downloads/`](docs/downloads/) |
| 2 | Fix/understand "Predicted values must be in range [0, 1]" | ◐ not reproducible; mitigated | checker + triage, [`audit F13`](docs/audit.html#F13); [`tests/test_site_js.py`](tests/test_site_js.py) |
| 3 | Unique name + short note per submission | ✅ | `gems.submission.make_filename/make_note`; `tests/test_submission.py` |
| 4 | Executive-summary subpage explaining exactly how to submit | ✅ | [`docs/executive_summary.html`](docs/executive_summary.html) |
| 5 | Why 5GEMSDOE == GEMSDOE1; are we copying work? | ✅ verified by blob SHA + pixel comparison | [`evidence/submission_similarity.json`](evidence/submission_similarity.json), [Results](docs/results.html) |
| 6 | 3–5 new geological hypotheses with layers, signature, catalogue-gap rationale, novelty, ranking | ✅ | [`docs/research/hypothesis_register.md`](docs/research/hypothesis_register.md) |
| 7 | Validate the top candidate on the spatially blocked holdout before any slot | ✅ pre-registered; results + controls | [`docs/research/preregistration_h18.md`](docs/research/preregistration_h18.md), [`evidence/hypothesis_h18_validation.json`](evidence/hypothesis_h18_validation.json) |
| 8 | External-data ideas: name the free official source and check it is obtainable | ✅ | register §5; [`evidence/ci/external_verification.json`](evidence/ci/external_verification.json) |
| 9 | Verify line by line from official sources; links for review; flag irregularities | ✅ | [Audit](docs/audit.html): 36 sourced claims, 21 flags ([`registry/`](registry/)) |
| 10 | Put this prompt in the README and read it every session | ✅ | bottom of this file; `AGENTS.md` |
| 11 | Up-to-date feed that removes manual checking | ◐ partial, by design | weekly `source-health` and daily `group-scan` workflows (**new; first run happens after merge to `main`** — the scanner's logic is tested offline); **no** DrivenData scraping (Terms of Use, [flag F09](docs/audit.html#F09)) |
| 12 | Store knowledge from official sources for reuse | ✅ | [`docs/knowledge/knowledge_base.md`](docs/knowledge/knowledge_base.md) |
| 13 | Clean GitHub Pages site with sources | ✅ | `scripts/build_site.py` (every number comes from evidence JSON) |
| 14 | Data placement (download script + prepare step) | ✅ re-run and verified | `scripts/download_competition_data.sh`, `scripts/prepare_data.py` |
| 15 | New strategy to beat 0.3049 / the leader | ◐ not achieved | no candidate can be claimed to beat the leader; see *Next steps* |
| 16 | PR → merge to main; suggestions and limitations | ✅ merged to `main` with a merge commit (the pre-registration commit stays an ancestor) | [the merged pull request from `arena/01a0efc4-16gemsdoe`](https://github.com/buffedlizard55-lab/16GEMSDOE/pulls?q=is%3Apr+is%3Amerged+head%3Aarena%2F01a0efc4-16gemsdoe); limitations and next steps are the next two sections; provenance note [F21](docs/audit.html#F21) |

## Core values in practice

* **Maximize P(Win).** Spend slots only on distinct, gated, format-verified files; run the uniqueness gate on everything; treat the holdout as necessary evidence, never proof; prefer experiments whose outcome teaches something (the A/B pair).
* **Own the outcome.** Reproduce before trusting (the prior H16-1 numbers were re-run and matched exactly), report failures (H18-1, H18-3b/c failed), and fix or flag what is broken instead of working around it.

## How to reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export GEMS_DATA_DIR=/path/with/room/for/1.5GB        # data stays out of git
bash scripts/download_competition_data.sh              # hash-pinned team bridge + public USGS-derived stacks
python scripts/prepare_data.py                         # verifies hashes, grids, irregularities
python scripts/run_spatial_holdout_and_build.py        # OOF surfaces + holdout (≈ 10 min on 2 CPUs)
python scripts/validate_h18.py                         # pre-registered H18 arms + gate
python scripts/validate_h18_exploratory.py             # controls (post-hoc, labelled)
python scripts/forensic_audit.py                       # fetch + hash-verify all group files, similarity matrix
python scripts/build_candidates.py                     # candidates + checks + uniqueness gate -> docs/data/submissions.json
python scripts/build_site.py && python scripts/check_site.py
python -m pytest -q                                    # full suite; tests marked `data` also need GEMS_DATA_DIR
python scripts/record_score.py h18-3a <score shown by DrivenData>   # the one manual step after an upload
```

## Repository map

| Path | Purpose |
|---|---|
| `src/gems/` | `metric.py` (official DTI), `holdout.py` (gate), `hypotheses.py` (H18 operators), `submission.py` (write/check/name), `forensics.py` (uniqueness gate), `footprint.py`, `paths.py` |
| `scripts/` | data download/prepare, holdout, H18 validation, forensic audit, candidate + site builders, CI scripts |
| `registry/` | hash-verified file registry, sourced-claims table, irregularities register, score ledger |
| `evidence/` | every measured result as JSON (+ `ci/` results committed back by GitHub Actions) |
| `docs/` | generated site, research/knowledge Markdown, downloads, retired `archive/` |
| `.github/workflows/` | `ci`, `external-verification`, `source-health`, `group-scan` |

## Limitations — and what this project needs access to

| Limitation | Effect | What would fix it |
|---|---|---|
| **No DrivenData login/API** | cannot download the data tab, submit, see scores, or compare the bridged `sample_submission.tif` with the original ([flag F02](docs/audit.html#F02)) | A person uploads files and runs `record_score.py`; someone with access records the SHA-256 of the data-tab files so they can be compared |
| **Terms of Use forbid bots** | no live leaderboard feed | Ask `info@drivendata.org` for written permission (draft below); until then snapshots are manual |
| **Agent sandbox reaches only GitHub/PyPI/npm** | official data hosts (USGS, GDR, 3DEP) are unreachable from the sandbox | Already solved for verification by running on GitHub Actions and committing results back (logs are not retrievable, results are) |
| **2 CPU / 3.9 GB, no GPU** | cannot retrain the CNN ensemble behind 0.1563 or the reference U-Net | A GPU notebook (Colab/Kaggle/cloud) writing predictions to a GitHub release; CI has 4 vCPU/16 GB but no GPU |
| **Short-lived GitHub credentials in the agent environment** | pushes/PRs fail after ~1 hour ("token no longer valid") | Reconnect GitHub in Arena when that happens |
| **Hidden labels and scorer unavailable** | every holdout is a proxy that recovers *known* faults ([F17](docs/audit.html#F17)) | Use live A/B scores to calibrate; never tune to hidden pixels |
| **No geologist on the team** | hypotheses are literature-grounded, not field-validated | Recruit one (the forum shows others doing the same) |

**Draft permission request** (send from the team's DrivenData-registered address): *"We maintain a public research repository for GEMS Prize #306. May we retrieve the public leaderboard page once per day by script to update a team dashboard, at no more than one request per day with an identifying User-Agent? If not, we will continue to update it manually."* → `info@drivendata.org`; rules questions → `gemsprize@nlr.gov`.

## Next steps (priority order)

0. **Confirm the automation once on the real runner.** Actions tab → run `group-scan` and `source-health` (*Run workflow*, branch `main`; they commit refreshed `docs/` data back to the branch they run on), then run `python scripts/scan_group_repos.py` yourself once to see the real output (it has only been exercised against an offline fake). GitHub Pages is already set to `main` / root with the legacy build (root `index.html` redirects to `docs/`). Future pull requests must use a **merge commit**, not squash: `tests/test_site_integrity.py` checks that the pre-registration commit remains an ancestor.
1. **Owner decision (today):** upload #1 and #2 (A/B) and record both scores; decide on #3. Choose the weekly pattern so that total uploads stay ≤ 3 per rolling 7 days per entity, and resolve [F08](docs/audit.html#F08) (multiple accounts) first.
2. **Calibrate the gate** from the first live pair. If H18-3a ≤ H16-1 live, the clustering prior does not transfer; fall back to H16-1 and revisit the proxy.
3. **Build and pre-register H18-5 (thermal anchors)** using the measured premise (35 % of footprint springs are > 3 km from any catalogued fault) and **H18-6 (TIGER road/rail suppression)** — both data sources are confirmed obtainable.
4. **Raw 3DEP DEM in CI** (H17-2 drainage deflection, better scarp/valley features): runners can reach the tiles; the sandbox cannot.
5. **Model upgrade on GPU:** the holdout shows topography carries most recoverable signal; train a scarp-aware CNN on DEM-derived inputs (the reference solution is a starting point), evaluated with `src/gems/holdout.py` and gated before any slot.
6. **Compliance:** prepare the gen-AI disclosure narrative and the winning-model documentation (finalists must deliver reproducible code — rules §3.5) before the deadline; pin SGMC to a specific release ([F14](docs/audit.html#F14)).
7. Enable the scheduled workflows (they run from `main`): `source-health`, `group-scan`.

## Session log

* **2026-09-30 (this session).** Re-ran and verified the data pipeline and holdout (bit-identical). Read all official sources (problem page, About, rules PDF, home page, forum rulings 11516/11524/11527/11528/11536, Terms of Use, USGS/OSTI papers). Found GitHub Actions can reach official hosts and used it to verify `labels.tif` against GDR (99.95 %). Pre-registered and ran H18-1/3a/3b/3c (one pass), then controls. Built hash-verified registry, forensic audit, browser checker, three candidates, the site, tests and workflows. See PR description for the multi-pass review.
* **2026-09-30 (publishing).** GitHub access returned. The sandbox had meanwhile been restored from a file snapshot: local history was lost and `docs/data/footprint.bin` was corrupted ([F21](docs/audit.html#F21)). Re-verified all 9 published files by SHA-256, regenerated the footprint payload byte-for-byte from the official template, re-ran the tests and the site build, re-created the commits on top of the remote branch (the pre-registration commit `6c5f74a` is original), then opened and merged the pull request with a merge commit.

---

<details><summary><strong>Original request (verbatim) — read at the start of every session</strong></summary>

```text
Review the repo. 

There should be an easy to download submission tif file as described by the prompt.  Read the entire prompt.

Here are the results from our groups submissions, separated by ....:

GEMSDOE1

[https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html)

GEMSDOE SCORE: 0.1563

....

[https://buffedlizard55-lab.github.io/6GEMSDOE/](https://buffedlizard55-lab.github.io/6GEMSDOE/)

6GEMSDOE SCORE: 0.0286

....

GEMSDOE3

[https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html)

GEMSDOE3 SCORE: 0.1193

1 · SUBMIT FIRST

f347b70daa

Pindrop nodes

....

GEMSDOE2

[https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html)

GEMSDOE2 SCORE: 0.1560

....

GEMSDOE3

[https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html)

GEMSDOE3 SCORE: 0.0830

2 · SUBMIT SECOND37f9d5b855

Pindrop catalogue-gap target SECOND SYSTEM

....

[https://buffedlizard55-lab.github.io/GEMSDOE4/](https://buffedlizard55-lab.github.io/GEMSDOE4/)

GEMSDOE 4 SCORE: 0.0343

....

GEMSDOE3

[https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html)

GEMSDOE3 SCORE: 0.1152

3 · CONTROL · UPLOAD LAST

4e03fc9705

Pindrop dense ridge control

....

[https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html)

5GEMSDOE SCORE: 0.1563

....

[https://buffedlizard55-lab.github.io/7GEMSDOE/](https://buffedlizard55-lab.github.io/7GEMSDOE/)

7GEMSDOE SCORE: 0.1461

....

[https://buffedlizard55-lab.github.io/8GEMSDOE/](https://buffedlizard55-lab.github.io/8GEMSDOE/)

8GEMSDOESCORE: 0.1563

....

[https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html)

9GEMSDOE SCORE: 0.0107

....

[https://buffedlizard55-lab.github.io/GEMSDOE10/](https://buffedlizard55-lab.github.io/GEMSDOE10/)

10GEMSDOE SCORE:

h16-continuation-20260927T065521077735Z-3431b83c7c: 0.0461

h20-dem10-scarp-thin-20260927T155223039488Z-ffc91a1686: 0.0921

H25-ctx-ridge-20260927T232947704150Z-6452ae1d00: 

h28-dotted-ridge-20260928T020256236880Z-6452ae1d00: 

wbg1

....

[https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html)

11GEMSDOE SCORE: 0.0202

....

[https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html)

12GEMSDOE SCORE:0.1294

r7-nms3-dem10-scarp_0c9199f14e62

[https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html)

12GEMSDOE SCORE:0.1294

r7-nms3-dem10-scarp_0c9199f14e62_allfinite

SDCF9

....

[https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html)

15GEMSDOE SCORE: 0.0782

gems-tso1-20260929T005627Z-conj_alteration_mag

smashi34

....

[https://buffedlizard55-lab.github.io/13GEMSDOE/](https://buffedlizard55-lab.github.io/13GEMSDOE/)

13GEMSDOE SCORE:

....

[https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html)

14GEMSDOE SCORE: 0.0020

smrtdoog5

....

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

We need to figure out why we keep scoring 0.1563, are we copying the same work over and over again?  we need to come up with different ideas, and not just the same idea tried a different way.

Need to figure out why 5GEMSDOE and  GEMSDOE1 have the same score.  We should not be generating the same score submissions, they should all be unique.

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.                      

Verify no hallucinations.    

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

We need to quickly look at the results and our results.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done so we should be able to figure out a way to score higher on the leaderboard using previous results and scoring that we have across the sites listed above.  We need to come up with distinct and unique strategies to score higher in this competition leaderboard.  We need to start doing heavy and deep research into the part of the project that matters the most, which is the scientific discovery of geothermal vents.  We should store all of our information and knowledge that we can gather from official verified sources.  This will serve as a starting point for other projects as well.  We need to think outside the box but still be grounded in proper scientific research, we are ultimately aiming for a top prize that many others are competing for.  So it's important to be contrarian but be smart about it.  We need to find sources of data that others are over looking or areas of the project when it comes to geothermal vents.  We need to do deep research and critical thinking and come up with new hypothesis to test.

Use these sites as a starting point for understanding how our group has generated submissions in the past.  

GEMSDOE1

[https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html)

GEMSDOE SCORE: 0.1563

....

[https://buffedlizard55-lab.github.io/6GEMSDOE/](https://buffedlizard55-lab.github.io/6GEMSDOE/)

6GEMSDOE SCORE: 0.0286

....

GEMSDOE3

[https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html)

GEMSDOE3 SCORE: 0.1193

1 · SUBMIT FIRST

f347b70daa

Pindrop nodes

....

GEMSDOE2

[https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html)

GEMSDOE2 SCORE: 0.1560

....

GEMSDOE3

[https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html)

GEMSDOE3 SCORE: 0.0830

2 · SUBMIT SECOND37f9d5b855

Pindrop catalogue-gap target SECOND SYSTEM

....

[https://buffedlizard55-lab.github.io/GEMSDOE4/](https://buffedlizard55-lab.github.io/GEMSDOE4/)

GEMSDOE 4 SCORE: 0.0343

....

GEMSDOE3

[https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html)

GEMSDOE3 SCORE: 0.1152

3 · CONTROL · UPLOAD LAST

4e03fc9705

Pindrop dense ridge control

....

[https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html)

5GEMSDOE SCORE: 0.1563

....

[https://buffedlizard55-lab.github.io/7GEMSDOE/](https://buffedlizard55-lab.github.io/7GEMSDOE/)

7GEMSDOE SCORE: 0.1461

....

[https://buffedlizard55-lab.github.io/8GEMSDOE/](https://buffedlizard55-lab.github.io/8GEMSDOE/)

8GEMSDOESCORE: 0.1563

....

[https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html)

9GEMSDOE SCORE: 0.0107

....

[https://buffedlizard55-lab.github.io/GEMSDOE10/](https://buffedlizard55-lab.github.io/GEMSDOE10/)

10GEMSDOE SCORE:

h16-continuation-20260927T065521077735Z-3431b83c7c: 0.0461

h20-dem10-scarp-thin-20260927T155223039488Z-ffc91a1686: 0.0921

H25-ctx-ridge-20260927T232947704150Z-6452ae1d00: 

h28-dotted-ridge-20260928T020256236880Z-6452ae1d00: 

wbg1

....

[https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html)

11GEMSDOE SCORE: 0.0202

....

[https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html)

12GEMSDOE SCORE:0.1294

r7-nms3-dem10-scarp_0c9199f14e62

[https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html)

12GEMSDOE SCORE:0.1294

r7-nms3-dem10-scarp_0c9199f14e62_allfinite

SDCF9

....

[https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html)

15GEMSDOE SCORE: 0.0782

gems-tso1-20260929T005627Z-conj_alteration_mag

smashi34

....

[https://buffedlizard55-lab.github.io/13GEMSDOE/](https://buffedlizard55-lab.github.io/13GEMSDOE/)

13GEMSDOE SCORE:

....

[https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html)

14GEMSDOE SCORE: 0.0020

smrtdoog5

....

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

We need to figure out why we keep scoring 0.1563, are we copying the same work over and over again?  we need to come up with different ideas, and not just the same idea tried a different way.

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

0.3049	is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website.  It should be unique, take unique approaches to generating a submission that can score higher than .3049.  

Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use.  It should solve the problem of having to manually check everything ourselves and having an up to date current feed.

Review the repo. 

The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.

Our Core Values

Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.                      

  

Verify no hallucinations.    

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We need to focus on being able to generate a submission into the competition.  

The site should be able to generate a TIF file that is required for submission.  It should be as easy as download to click a File to submit into the competition.  This needs to be in the executive summary or the very beginning of the site.  it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the submission form:

"Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Here is the submission page when i click submit file

New submission

File to submitNo file chosen

You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS, shape, and geotransform. You may wish to review the competition rules first.

Note (optional)

A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the contest. 

Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition.  The following is the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

We need to create a project that can compete and place top of the leaderboard.  We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.  

This is the guidelines we need to follow.[https://www.drivendata.org/competitions/306/competition-doe-gems/](https://www.drivendata.org/competitions/306/competition-doe-gems/)

Get familiar with the problem through the overview and problem description,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). You might also want to reference additional resources available on the about page,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/).

Download the data from the data,[https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/), tab.  

Create and train your own model. This reference solution,[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution) implements a simple approach.

Use your model to generate predictions that match the submission format.

Tell me what are you limitations and what you need access to during this project.  We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.  

this pdf outlines how submissions must be entered into the competition.  

[https://docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)

You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information.  this must be done autonomously and must be constantly reviewed and improved upon.  Provide suggestions and improvements and implement them.

❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (verified redirect to login)

See below for links from the above site.  See attached files for links from the above site.

[https://gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)

Download competition data from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (requires login) to data/

See links below for competition data:

[https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&amp;st=wz4kofki&amp;dl=0](https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&st=wz4kofki&dl=0)

[https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&amp;st=8junzdyw&amp;dl=0](https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0)

[https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&amp;st=rnino7ya&amp;dl=0](https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0)

[https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&amp;st=zj1lag1r&amp;dl=0](https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0)

[https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&amp;st=srhhir10&amp;dl=0](https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&st=srhhir10&dl=0)

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.                      

Verify no hallucinations.    

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Site creation

Create a github page for this repo that has clean ui, user friendly, simple and easy to use.  It should be organized and clean.  

It should include all relevant information in an easy to read format with official verified links as sources for review.  Work line by line verify everything no hallucinations.

**The single remaining blocker to training is data placement**: run `bash scripts/download_competition_data.sh` on any unrestricted machine into `data/`, then `python scripts/prepare_data.py` — after that the full train→inference→validate pipeline is ready to run (GPU needed for training; metric/losses/validation all verified working here on CPU).

you need to complete the above task by yourself.  Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.                      

Verify no hallucinations.    

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request.  Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project.  It should be worked on in this next session or the next session.  Work line by line verify everything no hallucinations.

```

</details>
