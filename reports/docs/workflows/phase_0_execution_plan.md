# Phase 0 — Staged Execution Plan

**Project:** ACRAS (Agentic Credit Risk & Analysis System)
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-29 · **Status:** Sequencing only — no implementation has started

This document sequences the approved `phase_0_implementation_plan.md` decisions into an execution order. Nothing here is code — it's the order of operations, the gate each stage must clear before the next one starts, and which ADR gets logged where. ADRs are assigned to the stage where the underlying fact actually gets _verified_, not batched at the end — this keeps the ADR log atomic and matches how the rest of this project has handled decisions so far.

---

## Stage Index

| Stage | Name                                               | Gate (one line)                                                                                     |
| ----- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 0     | Pre-Implementation Verification & Dependency Check | Every checklist item confirmed true or logged as an exception                                       |
| 1     | Repository Initialization & Structural Scaffold    | Repo tree matches spec exactly; docs live where they claim to                                       |
| 2     | Environment, Dependencies & Base Image             | `uv sync`, empty test run, and `docker build` all succeed clean                                     |
| 3     | Dataset Acquisition & DVC Remote                   | `dvc pull` succeeds from a simulated fresh clone                                                    |
| 4     | Data Contract — Great Expectations Suite           | Suite passes 100% against the real, valid dataset                                                   |
| 5     | The Gate Itself — Wiring & Adversarial Proof       | Corrupted fixture is rejected; valid data passes; the test is proven capable of failing             |
| 6     | Evidence-Bundle Schema Draft                       | Schema imports clean, type-checks, and instantiates with only Phase-0 fields populated              |
| 7     | MLflow Tracking Wiring                             | A real (dummy) run is visible in the local MLflow UI                                                |
| 8     | CI Assembly & First Green Run                      | GitHub Actions shows every job green on an actual push, not just locally                            |
| 9     | ADR Consolidation & Phase 0 Sign-Off               | Post-Implementation Review table fully populated; status table updated; exit criterion re-confirmed |

---

## Stage 0 — Pre-Implementation Verification & Dependency Check

**Goal:** Nothing has been built, so this stage exists to confirm the ground truth every later stage assumes — rather than discovering a false assumption mid-build, three stages deep.

**Actions:**

- Confirm `uv`, Python 3.12, Docker, and Git are installed and on `PATH`, with version numbers recorded.
- Confirm AWS account access is usable (able to create resources) — this only confirms the account itself; the actual least-privilege IAM user and bucket are created in Stage 3, not here.
- Confirm Kaggle account/API access works, and independently verify the "Company Bankruptcy Prediction" dataset's actual current row/column count and license terms still match what D-0.1 assumed — Kaggle datasets do occasionally change or get pulled, and this is cheap to check now versus expensive to discover mid-Stage-3.
- **Resolve D-0.5a's flagged uncertainty for real:** check Great Expectations' current released version and confirm whether the legacy Validator/ExpectationSuite API is still the recommended default entry point, or whether the Fluent/Core API has since become the primary path. Record the actual finding. If it contradicts D-0.5a's assumption, that gets corrected here, not silently discovered in Stage 4.
- Resolve the naming discrepancy noted above (confirm canonical project name).
- Confirm a remote (GitHub) repository exists — or will be created — before Stage 1 needs to push its first commit.

**ADR logged this stage:** None — this stage produces verified facts, not new decisions.

**Gate 0 (must pass before Stage 1):** every item above is either confirmed true, or has an explicit, written exception with its own resolution. No item is allowed to remain a silent assumption carried forward.

---

## Stage 1 — Repository Initialization & Structural Scaffold

**Goal:** Make the repository match what the planning documents already claim about it (Latent finding #1 in the Current State Audit), and resolve the `tier1_ml/` vs. `pipelines/training/` boundary (Latent finding #2) before any code exists to blur it.

**Actions:**

- `git init`; create the full declared directory tree (empty, structural only — `src/`, `tests/`, `reports/docs/...`, `.github/workflows/`).
- Move the existing seven planning documents into their declared `reports/docs/references/`, `reports/docs/architecture/`, and `reports/docs/runbooks/` paths.
- Establish the `tier1_ml/` vs. `pipelines/training/` boundary as a structural fact: a placeholder module/docstring in each stating its scope, so the boundary is documented in the code itself, not only in a planning file someone might not read.
- First commit.

**ADR logged this stage:** **ADR-010** — `tier1_ml`/`pipelines/training` boundary (training code produces the artifact; `tier1_ml` only serves it).

**Gate 1 (must pass before Stage 2):** the repo tree matches the declared structure exactly (no extra or missing top-level directories); every planning document is reachable at the path it references internally; one clean initial commit exists.

---

## Stage 2 — Environment, Dependencies & Base Image

**Goal:** A working, reproducible environment before any real logic is written into it.

**Actions:**

- Initialize `pyproject.toml` under `uv`; add the core dependency set (data/ML, DVC, Great Expectations, MLflow, Pydantic, FastAPI, pytest, ruff, pyright); commit the lockfile.
- Write a minimal Dockerfile on `python:3.12-slim` (D-0.8) — multi-stage, non-root user, no application code yet.
- Add the module-size check script referenced by the harness's CI step (script only — not wired into CI yet; that's Stage 8).

**ADR logged this stage:** None — D-0.2 and D-0.8 were already "no input required" confirmations, not new decisions; nothing new to log.

**Gate 2 (must pass before Stage 3):** `uv sync` completes cleanly; `uv run pytest` (zero tests) exits 0; `docker build` succeeds against the empty skeleton; `ruff check` and `pyright` both run clean on the (currently empty) `src/` tree.

---

## Stage 3 — Dataset Acquisition & DVC Remote

**Goal:** A real, versioned, remotely-reproducible dataset — not just a file on one machine.

**Actions:**

- Download the dataset verified in Stage 0; record its exact version/snapshot identifier.
- Provision the AWS S3 bucket and a least-privilege IAM identity scoped only to that bucket; credentials go through the environment/secrets path, never into the repo.
- `dvc init`; configure the S3 remote; `dvc add` the raw dataset; `dvc push`.
- Simulate a fresh clone in a separate directory and confirm `dvc pull` reconstructs the dataset from the remote alone.

**ADR logged this stage:** **ADR-011** — dataset pin (Kaggle Company Bankruptcy Prediction, exact version/row-count as verified in Stage 0, entity-type caveat restated). **ADR-012** — DVC remote (AWS S3, least-privilege IAM, credential-handling approach).

**Gate 3 (must pass before Stage 4):** `dvc pull` succeeds from the simulated fresh clone; the dataset's checksum is recorded in the ADR; a manual check of `git log`/`git diff` confirms no AWS credentials were ever committed.

---

## Stage 4 — Data Contract: Great Expectations Suite

**Goal:** Encode D-0.5's minimal, real expectation coverage against the actual acquired dataset.

**Actions:**

- Using the API generation confirmed in Stage 0, define the expectation suite: schema/dtype checks, null-rate thresholds, range checks on the key financial ratios, ID uniqueness.
- Run the suite against the Stage-3 dataset and resolve any failures against real data quirks (not against the suite's strictness — the suite encodes the contract; the data has to actually satisfy it).
- Save and version the suite alongside the code.

**ADR logged this stage:** **ADR-013** — Great Expectations API generation and expectation-suite scope, folding in whatever Stage 0 actually found (rather than what D-0.5a assumed, if they differ).

**Gate 4 (must pass before Stage 5):** the suite passes 100% against the real, valid dataset. A suite that has to be loosened to pass is a signal to stop and re-examine the data, not to weaken the contract.

---

## Stage 5 — The Gate Itself: Wiring & Adversarial Proof

**Goal:** Actually demonstrate Phase 0's Roadmap exit criterion, not just build the pieces that should theoretically produce it. This is where INV-7 stops being a stated rule and becomes an observed behavior.

**Actions:**

- Create a minimal `dvc.yaml` pipeline: a validation stage (runs the Stage 4 suite) gating a stub/no-op "training" stage that does nothing except exist as something to be blocked.
- Create a small, deliberately corrupted in-repo fixture (bad dtype, out-of-range value, null where none is allowed).
- Write the test proving: (a) the valid dataset passes the gate and reaches the stub training stage, (b) the corrupted fixture is rejected and never reaches it.
- **The check the Post-Implementation Review table specifically calls for:** temporarily disable the gate and confirm the same test then fails. A test that passes whether or not the gate exists is proving nothing — this step exists to rule that out, not to assume it away.

**ADR logged this stage:** None — this stage proves ADR-007 and ADR-013 work together; it doesn't establish a new decision.

**Gate 5 (must pass before Stage 6):** all three checks above pass — valid data through, corrupted data blocked, and the test independently shown capable of failing. This _is_ the Roadmap's Phase 0 exit criterion, demonstrated for real.

---

## Stage 6 — Evidence-Bundle Schema Draft

**Goal:** Implement D-0.6's resolution as actual code, so the ambiguity found in the audit can't recur for the next person (or the next session) reading the schema module.

**Actions:**

- Write the Pydantic schema module: the raw input fields the Stage 4 suite validates, a company identifier, and typed `Optional[...] = None` placeholders for every field later tiers will add (PD, bands, rating, ratios, persona verdicts).
- Add a module-level docstring stating explicitly that this is the **pre-v0 draft** — formal "v0" versioning begins at Tier 1 — so the versioning question this stage exists to close can't quietly reopen later.

**ADR logged this stage:** **ADR-014** — evidence-bundle schema versioning resolution (pre-v0 draft skeleton; formal v0 starts at Tier 1) and the exact field scope of the draft.

**Gate 6 (must pass before Stage 7):** the module imports cleanly; `pyright`/`ruff` pass; a smoke test instantiates it with only the fields Phase 0 can populate, and confirms every other field defaults to `None` without error.

---

## Stage 7 — MLflow Tracking Wiring

**Goal:** Prove the tracking plumbing works end to end before there's a real model to track.

**Actions:**

- Confirm local file-based tracking (`./mlruns`, gitignored) initializes correctly.
- Log one real run — e.g., the Stage 4 suite's pass/fail result and the dataset's checksum as tracked parameters/metrics — specifically so this stage produces a genuine tracked artifact, not an empty directory that merely looks configured.

**ADR logged this stage:** None — D-0.4 was already a "no input required" confirmation.

**Gate 7 (must pass before Stage 8):** `mlflow ui` displays the logged run locally, with the expected parameters and metrics visible.

---

## Stage 8 — CI Assembly & First Green Run

**Goal:** Everything proven locally in Stages 2–7 now has to prove itself in a clean CI environment, not just on the one machine that built it.

**Actions:**

- Assemble `.github/workflows/ci.yml`: lint (ruff) → type-check (pyright) → module-size check (Stage 2's script) → unit tests, including Stage 5's fixture-based gate test → Docker build (no push).
- Push to the GitHub remote confirmed in Stage 0.
- Watch the actual GitHub Actions run, not a local approximation of it.

**ADR logged this stage:** **ADR-015** — CI skeleton scope for Phase 0 (confirms the D-0.7 deferral: full `dvc repro`-in-CI wiring stays out of scope here, scheduled for Phase 5 alongside the calibration/divergence gates).

**Gate 8 (must pass before Stage 9):** every CI job is green on an actual triggered push in GitHub Actions. A green run only on a local machine does not satisfy this gate.

---

## Stage 9 — ADR Consolidation & Phase 0 Sign-Off

**Goal:** Close the loop between "decided," "built," and "recorded" before Phase 1 is allowed to start.

**Actions:**

- Confirm ADR-010 through ADR-015 are all correctly filed in `system_design.md`'s ADR log, each in the Accepted format already used for ADR-001 through ADR-009.
- Update `system_design.md`'s Current Implementation Status table: Phase 0 moves from "Not started" to its actual, honestly-reported outcome (including any partial/exception items logged in Stage 0).
- Fill in every row of `phase_0_implementation_plan.md`'s Post-Implementation Review table with the real "Actual" value, a Finding (even if the finding is "matches as designed"), and a Status — no row stays "_pending_."
- Independently re-run the Roadmap's own Phase 0 exit criterion one final time as the closing check, separate from Stage 5's proof, specifically to catch anything that regressed between Stage 5 and now.

**ADR logged this stage:** None new — this stage verifies the ledger is complete, it doesn't add to it.

**Gate 9 (Phase 0 complete; Phase 1 may begin):** every Post-Implementation Review row is populated with a real finding and no unresolved severity; `system_design.md`'s status table reflects reality; ADR-010 through ADR-015 are all filed; the exit criterion holds on the final re-run.
