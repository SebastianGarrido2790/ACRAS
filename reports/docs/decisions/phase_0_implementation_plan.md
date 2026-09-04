# Implementation Plan & Decisions — Phase 0 (Project Scaffolding & Data Contracts)

**Project:** ACRAS (Agentic Credit Risk & Analysis System)
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-29 · **Status:** Approved (2026-08-29) — ready for implementation

This is a living document. It translates Phase 0 of the Technical Roadmap into concrete, resolvable decisions, given the project's actual current state and its stated constraints (latency, cost, modularity, solo-builder timeline). Nothing below has been built. If a decision here is later revisited, the revision is logged in-place with a date, not silently overwritten — the same discipline already used for the ADR log.

**All decisions for Phase 0 have been formally reviewed and approved as of 2026-08-29.**

---

## 1. Current State Audit

An honest inventory of every file in Phase 0's scope — what exists, what's empty, and what's already showing a latent problem.

| File / Artifact                                                                                              | Status                                      | Notes                                                                                                                                                                                                                                                                         |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pyproject.toml`, `uv.lock`                                                                                  | Does not exist                              | —                                                                                                                                                                                                                                                                             |
| `.github/workflows/ci.yml`                                                                                   | Does not exist                              | —                                                                                                                                                                                                                                                                             |
| `Dockerfile`                                                                                                 | Does not exist                              | —                                                                                                                                                                                                                                                                             |
| `params.yaml`                                                                                                | Does not exist                              | —                                                                                                                                                                                                                                                                             |
| `dvc.yaml`, `.dvc/config`                                                                                    | Does not exist                              | No DVC remote has been chosen yet either (§3, D-0.3)                                                                                                                                                                                                                          |
| `data/raw/...` (DVC-tracked dataset)                                                                         | Does not exist                              | Dataset itself hasn't been selected yet (§3, D-0.1)                                                                                                                                                                                                                           |
| `src/schemas/evidence_bundle.py`                                                                             | Does not exist                              | Its intended content has a real ambiguity — see finding below                                                                                                                                                                                                                 |
| `great_expectations/` (expectation suite)                                                                    | Does not exist                              | GX version/API generation not yet chosen (§3, D-0.5)                                                                                                                                                                                                                          |
| `tests/unit/test_data_contract.py` (or equivalent)                                                           | Does not exist                              | This is what will demonstrate Phase 0's exit criterion                                                                                                                                                                                                                        |
| `reports/docs/references/canvas.md`, `project_charter.md`, `prd.md`, `user_story.md`, `technical_roadmap.md` | **Exist, but not where they claim to live** | These documents describe and reference paths under `reports/docs/references/` that don't actually exist as a real repository yet — they exist only as standalone files. This is the first thing Phase 0 has to resolve, before any of the rest of it makes sense (§3, D-0.0). |
| `reports/docs/architecture/system_design.md`                                                                 | Exists, same repo-placement gap             | Currently correctly shows every phase as "Not started" — accurate. Contains a genuine latent inconsistency in its own Data Flow section — see finding below.                                                                                                                  |
| `reports/docs/runbooks/challenges_and_solutions_guide.md`                                                    | Exists, same repo-placement gap             | —                                                                                                                                                                                                                                                                             |
| Project harness document                                                                                     | Exists, same repo-placement gap             | Listed here for inventory completeness only; not used as a decision authority anywhere in this document.                                                                                                                                                                      |

**Latent finding #1 — Evidence-bundle schema versioning is internally inconsistent.**
`technical_roadmap.md`'s Phase 0 task list calls for drafting the evidence-bundle schema as **"v0."** But `system_design.md`'s own Data Flow section (§5) describes the bundle reaching **"schema v0"** only _after_ Tier 1 has already populated it with a PD — i.e., after Phase 1, not Phase 0. Read literally, the two documents can't both be right: either Phase 0 produces "v0" and Tier 1 doesn't change the version number, or Phase 0 produces something that isn't yet "v0." This has to be resolved before a single line of the schema module is written, or the version field in the code will be wrong on day one. See D-0.6.

**Latent finding #2 — A structural ambiguity in where Tier 1 code actually lives.**
The project's stated structure has both a `src/tier1_ml/` module and a `pipelines/training/` stage, without a stated boundary between them. Once real code exists, "where does the training script live vs. where does the serving code live" needs an answer, or the two will develop overlapping responsibility. Resolved as part of D-0.0.

---

## 2. Roadmap Assessment for Phase 0

Distinguishing genuine gaps in the Roadmap's own wording from things that are already properly flagged elsewhere:

- **Real gap:** the schema-versioning inconsistency above. The Roadmap names a deliverable ("schema v0") without defining it precisely enough to survive being cross-checked against the rest of the document set.
- **Real gap:** the Roadmap lists "DVC-tracked dataset" as a Phase 0 deliverable but never mentions a DVC **remote**. A dataset that's DVC-tracked with no remote only versions metadata locally — it isn't actually reproducible from a fresh clone, which undercuts the entire point of using DVC. This needs a decision now, not an assumption. See D-0.3.
- **Real gap:** the Phase 0 exit criterion ("a deliberately corrupted data sample halts the pipeline") doesn't specify _how_ that has to be demonstrated — a local test run, or a CI-native one. That ambiguity is exactly what's driving scope creep risk into a phase that's supposed to be short. See D-0.7.
- **Not a gap (already correctly handled):** the Roadmap doesn't name a specific dataset. That's already an acknowledged open item in `system_design.md` §7, not an oversight — it's addressed properly below as D-0.1, not flagged as a Roadmap defect.

---

## 3. Decisions

### Decision Index

| ID    | Decision                                               | Status / Approved Choice                                                                                                      | Notes / Scope                                              |
| :---- | :----------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------- |
| D-0.0 | Repository initialization & documentation placement    | ✅ **Option A (Approved)**                                                                                                     | Repo initialized; docs placed in `reports/docs/...`        |
| D-0.1 | Public dataset selection                               | ✅ **Option A (Approved)**                                                                                                     | Kaggle Company Bankruptcy Prediction (~6,800 companies)    |
| D-0.2 | Python version & dependency management                 | ✅ **Python 3.12 + `uv` (Confirmed)**                                                                                         | Lockfile committed; strict typing                          |
| D-0.3 | DVC remote storage backend                             | ✅ **Option A (Approved — Revised)**                                                                                           | Local filesystem remote outside repo (superseding Option C/S3) |
| D-0.4 | MLflow tracking backend                                | ✅ **Local `./mlruns` (Confirmed)**                                                                                           | File-based experiment tracking                             |
| D-0.5 | Great Expectations version & expectation-suite scope   | ✅ **D-0.5a: Option A (Approved)**<br>✅ **D-0.5b: Option A (Approved)**                                                       | Validator API;<br>Minimal schema/dtype/null/range coverage |
| D-0.6 | Evidence-bundle schema versioning fix & v0-draft scope | ✅ **Option B (Approved)**                                                                                                     | Pre-v0 draft skeleton with typed `Optional` fields         |
| D-0.7 | CI skeleton scope for Phase 0                          | ✅ **Option A (Approved)**                                                                                                     | Lint + type-check + fixture-based GX unit test             |
| D-0.8 | Docker base image                                      | ✅ **`python:3.12-slim` (Confirmed)**                                                                                         | Debian-slim base; avoiding musl libc wheel issues          |

---

### D-0.0 — Repository Initialization & Documentation Placement

**Requires your approval:** Yes  
**Decision Status:** ✅ **Approved — Option A** (Repo initialized; documents moved to `reports/docs/...`)

**Question:** How do the seven already-approved planning documents (and any future ones) actually get into a real repository, and how is the `tier1_ml/` vs. `pipelines/training/` ambiguity (Latent finding #2) resolved?

**Options considered:**

| Option                                                                                                                                                                         | Trade-offs                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **[APPROVED] Option A**<br>Initialize the repo now, move all existing docs into their declared `reports/docs/...` paths as the very first commit, resolve the structural ambiguity in the same commit. | One clean, well-scoped first commit; the whole document set becomes internally consistent with reality immediately. Slightly more upfront work than starting with code.                                                                |
| Option B<br>Start writing Phase 0 code first, and move the docs over later once "there's something to commit."                                                                          | Feels faster to start; but leaves the documents in a state where they describe a repository that doesn't exist, which is exactly the inconsistency the audit above flags — deferring it doesn't remove it, it just delays noticing it. |

**Recommendation:** A.

**Resolution to Latent finding #2 (folded into this decision):** `pipelines/training/` produces the frozen model artifact (the FTI training stage); `src/tier1_ml/` contains only the FastAPI serving code and the thin inference wrapper around whatever artifact `pipelines/training/` produced. Training code and serving code are not the same files, and nothing in `tier1_ml/` may re-implement training logic — it only loads a registered artifact.

---

### D-0.1 — Public Dataset Selection

**Requires your approval:** Yes  
**Decision Status:** ✅ **Approved — Option A** (Kaggle "Company Bankruptcy Prediction")

**Question:** Which public dataset actually backs Tier 1 training?

**Options considered:**

| Option                                                                                                                                            | Trade-offs                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **[APPROVED] Option A**<br>**Kaggle "Company Bankruptcy Prediction"** (Taiwan Economic Journal, ~6,800 companies, 95 pre-computed financial-ratio features, binary label) | Real corporate financial ratios (fits the Financial/Domain Analyst Agent's needs directly); large enough sample size to make a calibration check (INV-3) statistically meaningful, which smaller sets aren't; well-benchmarked publicly, so a resulting AUC/Brier score is checkable against known baselines rather than trusted blind. Honest caveat: these are public companies, not strictly "SMEs" — the narrative gap is real and should be stated plainly wherever the dataset is described, not glossed over. |
| Option B<br>"Give Me Some Credit" (Kaggle)                                                                                                                 | Rejected: this is **individual/consumer** credit data, not company-level. Wrong entity type for a corporate credit-risk system — including it would mean building a demo that doesn't actually match what ACRAS claims to assess.                                                                                                                                                                                                                                                                                    |
| Option C<br>LendingClub loan data                                                                                                                          | Rejected for the same reason as B — consumer/personal loans, not corporate.                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Option D<br>UCI "Statlog German Credit Data"                                                                                                               | Rejected: only ~1,000 samples, largely individual-borrower purpose codes. Too small to produce a meaningful calibration check (Brier score / reliability curve need enough data per bucket to be trustworthy), which INV-3 now depends on directly.                                                                                                                                                                                                                                                                  |
| Option E<br>Smaller/synthetic "SME loan default" sets on Kaggle                                                                                            | Considered and set aside: several exist, but sample sizes and label-generation methodology are inconsistently documented, which is a real risk given how much of this project's credibility (calibration, divergence golden-set design) depends on trusting the underlying data.                                                                                                                                                                                                                                     |

**Recommendation:** A, with the entity-type caveat stated explicitly and consistently everywhere the dataset is referenced (README, `canvas.md` if revisited, model card) — this is a "closest available public proxy," not an SME dataset, and saying so plainly is more credible than letting it pass unremarked.

---

### D-0.2 — Python Version & Dependency Management

**Requires your approval:** No — recorded for completeness.  
**Decision Status:** ✅ **Confirmed** (Python 3.12 + `uv`)

**Decision:** Python 3.12, managed with `uv`, lockfile committed. There is no meaningful alternative worth presenting: this was already the project's working convention, and reopening it now would cost time without a real question behind it.

---

### D-0.3 — DVC Remote Storage Backend

**Requires your approval:** Yes  
**Decision Status:** ✅ **Approved (Revised) — Option A** (Local filesystem remote outside the repo; superseding initial Option C approval)

**Question:** Where does the DVC-tracked dataset actually live, so `dvc pull` works from a fresh clone (Roadmap Assessment gap above)?

**Options considered:**

| Option                                                    | Trade-offs                                                                                                                                                                                                                                                                                                                                                                                          |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **[REVISED APPROVAL] Option A**<br>Local filesystem remote (a directory outside the repo) | Zero cost, zero setup, zero external accounts. A dedicated directory outside the repo working tree provides physical isolation, strictly satisfying DVC's reproducibility contract (`dvc pull` reconstructs data from an external source) without cloud credential management or OAuth friction.                                                                                                    |
| Option B<br>Google Drive remote (`dvc-gdrive`)                     | Free (15GB), technically "cloud," but OAuth token setup and Google's API rate limits on the Drive backend are a well-documented source of friction — a real risk of losing time to plumbing rather than to the project itself.                                                                                                                                                                      |
| **[SUPERSEDED] Option C**<br>AWS S3 remote                                          | At this data scale (a few hundred MB at most), cost is negligible — realistically a few cents a month. Demonstrates real cloud credential handling and a genuinely reproducible remote. Requires an AWS account and careful credential handling (never committed — same principle already applied to every other secret in this project). Initially approved, but superseded due to absence of an active AWS account. |

**Recommendation:** Option A (Revised). Option C was initially selected to demonstrate cloud credential handling, but without an active AWS account, provisioning S3 stalls Stage 3 / Gate 3 on an unavailable external dependency. Reopening the choice between Google Drive and a local filesystem remote: Google Drive's OAuth setup and API rate limits add friction for a demo dataset that changes rarely. A local filesystem remote residing outside the repository root completely satisfies DVC's reproducibility requirement (verifying that the working copy is not the source of truth) with zero external friction.

---

### D-0.4 — MLflow Tracking Backend

**Requires your approval:** No — recorded for completeness.  
**Decision Status:** ✅ **Confirmed** (Local `./mlruns`)

**Decision:** Local file-based tracking (`./mlruns`, gitignored). A remote MLflow tracking server would be pure overhead for a single developer on a single machine with no concurrent experiments to coordinate — there's no real alternative worth weighing here.

---

### D-0.5 — Great Expectations Version & Expectation-Suite Scope

**Requires your approval:** Yes  
**Decision Status:** ✅ **Approved — D-0.5a: Option A (Validator API) & D-0.5b: Option A (Minimal, real coverage)**

**Sub-decision D-0.5a — API generation.**  
**Status:** ✅ **Approved — Option A**

| Option                                                            | Trade-offs                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **[APPROVED] Option A**<br>The older, widely-documented Expectation Suite / Validator API | More Stack Overflow answers and tutorials to fall back on if something goes wrong mid-build — lower risk of losing time to undocumented rough edges while solo and on a schedule.                                                                                                                                                                                                                                                  |
| Option B<br>The newer Fluent/Core API (GX 1.x)                             | Cleaner API design and more "current" to reference, but younger, with a thinner troubleshooting trail. **Flag, not a claim:** which API generation ships as the default in the current GX release may have shifted since this plan was written — this should be verified against GX's actual current documentation at implementation time rather than assumed from this document, per the project's own 80%-confidence discipline. |

**Recommendation:** A, specifically to minimize debugging risk during a phase that's supposed to be short — but verify at implementation time that this is still the more stable choice, rather than treating this recommendation as self-evidently current.

**Sub-decision D-0.5b — Expectation coverage.**  
**Status:** ✅ **Approved — Option A**

| Option                                                                                                                        | Trade-offs                                                                                                                                                                                                                         |
| ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **[APPROVED] Option A**<br>Minimal, real coverage: schema/dtype checks, null-rate thresholds, range checks on key financial ratios, ID uniqueness.    | Directly satisfies the Phase 0 exit criterion (prove the halt-on-bad-data mechanism works) without over-building.                                                                                                                  |
| Option B<br>Comprehensive coverage: also add statistical distribution-drift checks, cross-column consistency rules, outlier detection. | More thorough, but this is production-monitoring territory that the Roadmap already schedules elsewhere (Phase 5/production monitoring) — building it now risks quietly absorbing later-phase scope into an already-tight Phase 0. |

**Recommendation:** A. Extend to B's checks later, if and when Phase 5's monitoring work actually calls for them — not preemptively.

---

### D-0.6 — Evidence-Bundle Schema Versioning Fix & v0-Draft Scope

**Requires your approval:** Yes  
**Decision Status:** ✅ **Approved — Option B** (Pre-v0 draft skeleton with typed `Optional` placeholders)

**Question:** How to resolve Latent finding #1, and what exactly does Phase 0 draft?

**Options considered:**

| Option                                                                                                                                                                                                                                                          | Trade-offs                                                                                                                                                                                                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Option A<br>Renumber: shift `system_design.md`'s existing v0/v1/v2 up by one (Tier 1 output → v1, Tier 2 → v2, Tier 3 → v3), so "v0" cleanly means "the Phase 0 draft."                                                                                                  | Produces the most intuitive numbering (version number == tier number). Cost: requires editing already-finished, previously-approved documents (`system_design.md` §5, and any place versions are mentioned) for what is ultimately a cosmetic renumbering — reopening signed-off documents for this is a worse trade than the alternative below. |
| **[APPROVED] Option B**<br>Leave the existing documents untouched. Define, precisely, that Phase 0 produces a **pre-v0 draft skeleton** — and "v0" as a formally versioned schema first materializes once Tier 1 populates it in Phase 1, exactly as `system_design.md` already states. | Zero edits to already-approved documents. Requires only one precise definition (this entry, plus a docstring in the schema module itself) rather than a renumbering sweep. Keeps the discipline of "ADRs/approved docs are superseded, not silently edited" fully intact.                                                                        |

**Recommendation:** B. This is also consistent with how the rest of this project has handled revisiting decisions — add a precise clarification, don't retroactively rewrite what's already signed off.

**Sub-decision — what does the pre-v0 draft actually contain?** Only what Phase 0 can populate and validate: the raw input fields the GX suite checks (the fields present in the D-0.1 dataset), a company identifier, and `Optional[...] = None` placeholder fields for everything later tiers will add (PD, bands, rating, ratios, persona verdicts) — typed now so the schema is importable and type-checkable from day one, without requiring Tiers 1–3 to exist yet. This has no real alternative worth presenting: it's the only version of "draft the shared contract before the tiers that populate it exist" that actually works.

---

### D-0.7 — CI Skeleton Scope for Phase 0

**Requires your approval:** Yes  
**Decision Status:** ✅ **Approved — Option A** (Lint + Type-check + Fixture Unit Test)

**Sub-decision D-0.7a — Python version matrix.** Target 3.12 only; this is an internal project, not a published library needing multi-version compatibility testing. Confirmed.

**Main question:** Does Phase 0's CI need to run the actual GX-gate-halts-bad-data demonstration as a live pipeline step, or is a local/CI-run unit test sufficient?

| Option                                                                                                                                                                                                                                                                                                        | Trade-offs                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **[APPROVED] Option A**<br>Lint + type-check + a unit test (using a small, in-repo corrupted fixture, not the full DVC-tracked dataset) that proves the GX gate rejects bad data. Full `dvc repro`-in-CI wiring deferred to Phase 5, alongside the calibration/divergence gates that are already scheduled to be wired into CI there. | Keeps Phase 0 inside its 3–4 day estimate. Avoids building the "give CI runners access to the DVC remote and its credentials" plumbing twice — once now, once properly at Phase 5. Fully satisfies the literal exit criterion, since a fixture-based unit test does demonstrate the gate halting bad data. |
| Option B<br>Build full `dvc repro`-in-CI now, including CI's access to the D-0.3 remote and its credentials.                                                                                                                                                                                                           | Proves the exit criterion in the most rigorous possible environment immediately. Costs real setup time now (CI secrets, remote access) against an already-tight phase, for a robustness gain that Phase 5 was going to deliver anyway.                                                                     |

**Recommendation:** A. This is the direct fix for the Roadmap Assessment's third finding — the exit criterion's wording doesn't require the more expensive path, and choosing the cheaper one that still satisfies it literally is the correct call given the schedule risk already on record in the Roadmap.

---

### D-0.8 — Docker Base Image

**Requires your approval:** No — recorded for completeness.  
**Decision Status:** ✅ **Confirmed** (`python:3.12-slim`)

**Decision:** `python:3.12-slim`. Alpine is lighter but its musl libc causes real, well-documented binary-wheel friction with NumPy/scikit-learn/XGBoost — not a hypothetical risk, a known one. Distroless is more hardened but has no shell, which actively hurts debugging during a phase where the code is still being actively iterated on. Slim is the only option without a real downside at this stage; hardening to distroless can be revisited at Phase 7 close-out if desired.

---

## 4. What Happens After Approval

1. You approve, reject, or amend each decision above (approving the block of "no input required" defaults counts as confirming them).
2. Every approved decision that establishes a new project-level fact (dataset choice, DVC remote, GX version/scope, the schema-versioning resolution, CI scope) is logged as a new ADR entry (ADR-010 onward) in `system_design.md`, per its existing Update Protocol — approved decisions become the same kind of durable record as ADR-001 through ADR-009, not left standing only in this document.
3. Repository initialization happens first (D-0.0), moving the existing planning documents into the paths they already claim to occupy.
4. Phase 0 implementation proceeds task-by-task against the Roadmap's Phase 0 list, using the decisions locked here as fixed inputs — no further open questions should remain once this document is approved.
5. `system_design.md`'s status table is updated from "Not started" to its actual, honestly-reported outcome only once Phase 0's exit criterion is demonstrated, not before.
6. The Post-Implementation Review below is run before Phase 0 is declared complete and Phase 1 begins.

---

## 5. Post-Implementation Review & Remediation Records

_To be completed at the close of Phase 0 implementation, before Phase 1 begins. Not yet applicable — nothing has been built. This section exists now as the protocol that will be run, not as findings._

**Protocol:** cross-check the actual implemented artifacts against what this document decided, row by row:

| Check                                      | Expected (per this plan)                                                                                                           | Actual (as implemented) | Finding | Severity | Remediation | Status |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------- | -------- | ----------- | ------ |
| Dataset matches D-0.1                      | Kaggle Company Bankruptcy Prediction, version-pinned                                                                               | _pending_               |         |          |             |        |
| Evidence-bundle schema matches D-0.6 scope | Pre-v0 draft, `Optional` placeholders for Tiers 1–3 fields                                                                         | _pending_               |         |          |             |        |
| GX suite matches D-0.5b scope              | Schema/dtype/null/range/uniqueness only — no drift checks                                                                          | _pending_               |         |          |             |        |
| CI matches D-0.7 scope                     | Lint + type-check + fixture-based unit test only                                                                                   | _pending_               |         |          |             |        |
| DVC remote matches D-0.3                   | Local filesystem remote outside repo (Option A revised)                                                                            | _pending_               |         |          |             |        |
| Repo structure matches D-0.0               | `pipelines/training/` vs `tier1_ml/` boundary respected                                                                            | _pending_               |         |          |             |        |
| Exit criterion genuinely demonstrated      | Corrupted fixture _actually_ fails the gate — the test itself must be shown to fail if the gate is removed, not just shown to pass | _pending_               |         |          |             |        |

No finding in this table gets marked "Resolved" from a description alone — each needs the actual file/line checked before Phase 0 is signed off and Phase 1 starts.
