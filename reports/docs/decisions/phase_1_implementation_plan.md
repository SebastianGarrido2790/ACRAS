# Implementation Plan & Decisions — Phase 1 (Tier 1: Frozen ML Core)

**Project:** ACRAS (Agentic Credit Risk & Analysis System)
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-09-25 · **Status:** Awaiting approval — no implementation has started

Same discipline as Phase 0's plan: nothing below has been built, every decision is either approved, amended, or rejected before a line of Phase 1 code is written, and decisions marked "no input required" are recorded for completeness, not silently assumed.

---

## 1. Current State Audit

| File / Artifact                       | Status                                     | Notes                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/pipelines/feature/`              | Exists, empty scaffold                     | No feature-engineering logic yet.                                                                                                                                                                                                                                                                                                                                                                                            |
| `src/pipelines/training/__init__.py`  | Exists — boundary docstring only (ADR-010) | No training logic yet.                                                                                                                                                                                                                                                                                                                                                                                                       |
| `src/tier1_ml/__init__.py`            | Exists — boundary docstring only (ADR-010) | No serving code yet.                                                                                                                                                                                                                                                                                                                                                                                                         |
| `src/tier1_ml/api.py` (or equivalent) | Does not exist                             | —                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `src/schemas/evidence_bundle.py`      | Exists (Phase 0)                           | `pd`, `credit_rating`, `pd_band` already stubbed `Optional` — this is what Phase 1 populates.                                                                                                                                                                                                                                                                                                                                |
| MLflow registry                       | Only the Phase 0 Stage 7 dummy run exists  | No real model has been trained or registered.                                                                                                                                                                                                                                                                                                                                                                                |
| `data.csv` (DVC-tracked)              | Exists, schema-validated (6,819 × 96)      | GX validated schema/dtype/null/range/uniqueness — **not** class balance, multicollinearity, or anything else a modeling decision depends on. That's this phase's job, not something to assume from Phase 0's contract.                                                                                                                                                                                                       |
| `pyproject.toml`                      | Exists                                     | Two findings: **LightGBM is not a dependency**, despite being named as a Roadmap candidate — a real decision, not an oversight to just fix silently (§3, D-1.1). Separately, **`dvc[s3]` is still the declared extra** even though D-0.3 was revised to a local filesystem remote — a small, low-priority leftover from a reversed decision, worth a one-line cleanup (`dvc[s3]` → `dvc`) whenever convenient, not blocking. |
| `params.yaml`                         | **Does not exist**                         | Referenced by the project's own Coding Conventions ("no hardcoded thresholds... source from `params.yaml`"), but Phase 0 never actually created it — Phase 0 had no real tunable parameters yet. Phase 1 is the first phase that does (split ratios, seed, hyperparameters, calibration method), so this phase has to create it, not inherit it.                                                                             |
| `tests/unit/`, `tests/integration/`   | Exist, empty scaffolds                     | No Tier-1-specific tests yet.                                                                                                                                                                                                                                                                                                                                                                                                |
| `system_design.md` status table       | Phase 1: "Not started"                     | Accurate.                                                                                                                                                                                                                                                                                                                                                                                                                    |

## 2. Decision Log Summary (Inherited from Phase 0)

Carried forward, not relitigated: dataset is Kaggle Company Bankruptcy Prediction, 6,819×96 (ADR-011); Python 3.12/`uv` (D-0.2); the `tier1_ml`/`pipelines/training` boundary — training code produces the artifact, `tier1_ml` only ever serves it (ADR-010); full CI-blocking automation for promotion gates was deliberately deferred to Phase 5 (D-0.7/ADR-015) — Phase 1 must _demonstrate_ its calibration gate works, but doesn't need to wire it into merge-blocking CI yet. The one item Phase 0 explicitly left open for this phase: the XGBoost-vs-LightGBM model choice (`system_design.md` §7) — that's resolved below, not inherited as a foregone conclusion.

## 3. Roadmap Assessment for Phase 1

- **Real gap:** the candidate list ("XGBoost/LightGBM") skips a naturally-calibrated baseline. Given calibration is the exit criterion's entire point, comparing against a simple model whose raw output is already close to a probability by construction is cheap and diagnostically useful — the Roadmap's wording forecloses this without discussion.
- **Real gap:** the Roadmap's task list ("build the FastAPI endpoint... write endpoint tests") doesn't distinguish training-time data validation (GX, INV-7) from inference-time input validation. GX gates the training pipeline; it says nothing about a live request hitting the serving endpoint with a malformed payload. That's a separate validation surface the Roadmap's wording doesn't name.
- **Real gap:** `params.yaml` isn't mentioned anywhere in Phase 1's task list, despite this being the first phase with real tunable values (split ratios, seed, calibration method, hyperparameters) that the project's own Coding Conventions say must never be hardcoded.
- **Not a gap (correctly left open):** the Roadmap doesn't discuss class-imbalance handling or the calibration-split strategy's statistical validity on a small dataset. That's appropriately a Phase 1 modeling decision, not something planning-stage wording should have pre-specified.

## 4. Decisions

### Decision Index

| ID    | Decision                                             | Approval Required?             |
| ----- | ---------------------------------------------------- | ------------------------------ |
| D-1.0 | Establish `params.yaml`                              | No — recorded for completeness |
| D-1.1 | Model candidate set                                  | Yes                            |
| D-1.2 | Data-splitting & calibration strategy                | Yes                            |
| D-1.3 | Class-imbalance handling                             | Yes                            |
| D-1.4 | Post-hoc calibration method                          | Yes                            |
| D-1.5 | PD-to-credit-rating mapping                          | Yes                            |
| D-1.6 | Model serialization & serving boundary               | Yes                            |
| D-1.7 | Calibration check as a standalone, testable function | No — recorded for completeness |
| D-1.8 | FastAPI request/response schema strictness           | Yes                            |
| D-1.9 | Endpoint test scope                                  | No — recorded for completeness |

---

### D-1.0 — Establish `params.yaml`

**Requires approval:** No — recorded for completeness. This is the audit-driven action item from §1: create the file now, since Phase 1 is the first phase with real values to put in it (populated by the decisions below, not invented here).

---

### D-1.1 — Model Candidate Set

**Question:** Which models actually get trained and compared?

| Option                                                        | Trade-offs                                                                                                                                                                                                                                                                                                                          |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. XGBoost + LightGBM only, as the Roadmap names.             | Matches the plan as written; skips the diagnostic value of a simpler baseline.                                                                                                                                                                                                                                                      |
| B. XGBoost + LightGBM + a Logistic Regression baseline.       | Logistic Regression's raw output is already close to a calibrated probability by construction — comparing it against the boosted-tree candidates' _pre-calibration_ output directly shows how much distortion tree-based boosting introduces, which is exactly the failure mode INV-3 exists to catch. Costs almost nothing to add. |
| C. XGBoost only — drop LightGBM to avoid adding a dependency. | Simplest, but discards a real comparison point for a trivial `pyproject.toml` change.                                                                                                                                                                                                                                               |

**Recommendation:** B. **Sub-decision:** add `lightgbm` to `pyproject.toml`'s dependencies now — a one-line, uncontested mechanical step, not a separate decision needing its own analysis.

---

### D-1.2 — Data-Splitting & Calibration Strategy

**Question:** How is the data divided to train, tune, calibrate, and evaluate — honestly, on a dataset this size?

This dataset is known for a small positive (bankrupt) class relative to the whole — verify the exact ratio during EDA rather than trust a number asserted here, but plan the strategy assuming real imbalance, not a comfortable 50/50 split. A naive three-way split (train/calibration/test) risks leaving very few positive examples in whichever slice gets the short end, which would make both the calibration curve and the test-set metrics unstable — exactly the wrong place to be sloppy given calibration is a release gate, not a nice-to-have.

| Option                                                                                                                | Trade-offs                                                                                                                                                                                                                                   |
| --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Naive three-way split (e.g., 60/20/20, train/calibration/test), stratified by label.                               | Simple, but on a small imbalanced dataset this can leave a thin positive-class count in the calibration and/or test slice, undermining the reliability of the very check (INV-3) this phase exists to implement.                             |
| B. `CalibratedClassifierCV`-style cross-validated calibration (e.g., 5-fold), with a separate held-out test set only. | Makes efficient use of every positive example across folds rather than permanently sequestering a chunk of them into one split; standard, well-supported approach for exactly this situation (small, imbalanced data, calibration required). |

**Recommendation:** B. **Sub-decision (no input required — unambiguous given the constraint):** every split/fold must be stratified by the target label. There's no version of this dataset's imbalance where an unstratified split is defensible.

---

### D-1.3 — Class-Imbalance Handling

**Question:** How does training account for the class imbalance found in D-1.2?

| Option                                                                                                           | Trade-offs                                                                                                                                                                                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Class weighting (`scale_pos_weight` for XGBoost/LightGBM, `class_weight="balanced"` for Logistic Regression). | Adjusts the loss function without synthesizing or discarding real data points — compatible with a subsequent calibration step, since the model still sees the true data distribution.                                                                                                                           |
| B. Oversampling (e.g., SMOTE).                                                                                   | Synthesizes new minority-class points, which changes what the model's raw output probability actually means relative to the true population base rate — that distortion then has to be corrected for during calibration, adding a real risk of getting calibration subtly wrong in a way that's hard to detect. |
| C. Undersampling the majority class.                                                                             | Throws away real, already-scarce data — a worse trade than B for a dataset this size.                                                                                                                                                                                                                           |
| D. No adjustment; rely on calibration and threshold tuning alone.                                                | Worth running as a comparison baseline, not adopting outright — some tree models handle imbalance reasonably well unassisted, and this project's own evaluate-before-assuming discipline says to check that empirically rather than assume weighting is strictly necessary.                                     |

**Recommendation:** A, with D trained and compared as a baseline — not asserted as sufficient, tested against A and reported honestly regardless of which wins.

---

### D-1.4 — Post-Hoc Calibration Method

**Question:** Platt scaling or isotonic regression, if the raw model fails the calibration check (as anticipated in the Runbook)?

| Option                                                                                | Trade-offs                                                                                                            |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| A. Platt scaling (sigmoid).                                                           | Fits only two parameters — safer on a small calibration fold, less prone to overfitting the calibration curve itself. |
| B. Isotonic regression.                                                               | More flexible, non-parametric — but needs more data to avoid overfitting, a real risk given this dataset's size.      |
| C. Fit both; keep whichever wins on held-out Brier score; document which won and why. | Costs almost nothing extra (both are cheap to fit) and replaces a guess with a measured answer.                       |

**Recommendation:** C — this is a case where "try both and let the data decide" is genuinely the correct engineering answer, not just the more thorough-looking one, because the cost of doing so is negligible.

---

### D-1.5 — PD-to-Credit-Rating Mapping

**Question:** How does a calibrated PD become a rating bracket (`credit_rating` in the evidence bundle, PRD FR4)?

| Option                                                                                                                                                                                        | Trade-offs                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Fixed, documented PD thresholds inspired by public rating-agency conventions (e.g., roughly: PD < 0.1% → AAA-band, ~0.3–1% → BBB-band, ~1–5% → BB-band, ~5–15% → B-band, >15% → CCC-band). | Externally recognizable and stable across retraining — the whole point of calibration (INV-3) is that the PD number means something outside the model, and a fixed threshold table preserves that. **Flag, not a claim:** the specific numbers above are illustrative and drawn from general rating-agency convention, not a verified or licensed reproduction of any agency's actual methodology — verify and adjust ranges deliberately during implementation, and state clearly in any documentation that these are illustrative bands, not a claim of methodological equivalence to a real rating agency. |
| B. Data-driven bucketing off the training set's own PD distribution (e.g., quantiles → letter grades).                                                                                        | The mapping would shift every time the model retrains on new data, since it's relative to that training run's distribution rather than fixed — undermines the external legibility a "credit rating" is supposed to have.                                                                                                                                                                                                                                                                                                                                                                                      |

**Recommendation:** A, with the honesty caveat stated as part of the mapping's own documentation, not buried in this planning document alone. Store the thresholds as a versioned config (in `params.yaml` or a small dedicated module), never as inline magic numbers in the mapping function.

---

### D-1.6 — Model Serialization & Serving Boundary

**Question:** Does the FastAPI service load the model through MLflow's client at runtime, or from a lean exported artifact?

| Option                                                                                                                                                                                          | Trade-offs                                                                                                                                                                             |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. `tier1_ml` loads directly from the MLflow Model Registry (`mlflow.pyfunc.load_model`) at startup.                                                                                            | Tightly couples the serving container to MLflow's client library and its own dependency tree, at runtime, for a container whose whole job is to be a lean, fast-starting microservice. |
| B. MLflow is used for tracking and registry during training only; at promotion, export a lean artifact (`joblib`) that `tier1_ml` loads directly — zero MLflow dependency in the serving image. | Matches ADR-010's boundary (`tier1_ml` is strictly a serving module) and keeps the serving container's dependency footprint, image size, and cold-start time smaller.                  |

**Recommendation:** B. **Sub-decision (no input required):** `joblib` over ONNX for the export format — ONNX's cross-runtime portability solves a problem this single-service Python deployment doesn't have; `joblib` is simpler and fully sufficient here.

---

### D-1.7 — Calibration Check as a Standalone, Testable Function

**Requires approval:** No — recorded for completeness. Directly follows from the Roadmap Assessment's third finding and Phase 5's already-stated need to wire this into CI later: it has to be an isolated, pure function (inputs: true labels and predicted probabilities; output: a calibration verdict), importable by both the training script and, later, a CI test — never inline logic buried in a training notebook. No real alternative serves both uses.

---

### D-1.8 — FastAPI Request/Response Schema Strictness

**Question:** How strictly typed is the live inference request, given GX only validates the training-time contract, not live requests?

| Option                                                                                     | Trade-offs                                                                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| A. A fully-expanded Pydantic model with all ~95 named feature fields.                      | Maximum type safety at the API boundary, but duplicates the feature list in a second hand-maintained place — exactly the kind of drift risk this project has caught before (the ACRAS name, the schema-version numbering, the enum spelling). |
| B. A thin wrapper (`company_id`, `raw_features: dict[str, float                            | int]`) matching the evidence bundle's own shape, plus a runtime validator checking `raw_features`'s keys against one canonical feature list imported by both training and serving code.                                                       | Real validation, no second copy of the feature list to drift out of sync. |
| C. No validation beyond basic typing, relying on the model to fail naturally on bad input. | Rejected outright — inconsistent with the project's own validator-sandwich discipline; input guardrails aren't optional just because this is an internal service.                                                                             |

**Recommendation:** B.

---

### D-1.9 — Endpoint Test Scope

**Requires approval:** No — recorded for completeness. Unit tests for the D-1.7 calibration-check function and the D-1.5 rating-mapping function; an integration test hitting the real FastAPI endpoint (loaded against a test-mode model artifact) with both a valid and a deliberately malformed payload. This is the direct, uncontested reading of "write endpoint tests" — no real alternative approach worth presenting.

---

## 5. What Happens After Approval

1. You approve, amend, or reject each decision above.
2. Every approved decision that establishes a new project-level fact is logged as a new ADR entry — starting at **ADR-016** (confirm this is still the next open slot in your actual ledger before writing these in; it was open as of the last review but hasn't been independently re-checked this turn).
3. `params.yaml` is created (D-1.0), populated by the concrete values these decisions fix (split ratio/fold count, seed, calibration method, rating thresholds).
4. Phase 1 implementation proceeds against the Roadmap's task list using these decisions as fixed inputs.
5. `system_design.md`'s status table updates from "Not started" to its actual outcome only once Phase 1's exit criterion is demonstrated.
6. The Post-Implementation Review below runs before Phase 1 is declared complete and Phase 2 begins.

---

## 6. Post-Implementation Review & Remediation Records

_To be completed at the close of Phase 1 implementation. Not yet applicable — nothing has been built._

| Check                                                   | Expected (per this plan)                                                                                                                                                                   | Actual    | Finding | Severity | Remediation | Status |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ------- | -------- | ----------- | ------ |
| Model candidates match D-1.1                            | XGBoost, LightGBM, Logistic Regression all trained and compared                                                                                                                            | _pending_ |         |          |             |        |
| Splitting/calibration strategy matches D-1.2            | Cross-validated calibration, stratified folds                                                                                                                                              | _pending_ |         |          |             |        |
| Imbalance handling matches D-1.3                        | Class-weighted models compared against unweighted baseline                                                                                                                                 | _pending_ |         |          |             |        |
| Calibration method matches D-1.4                        | Both Platt and isotonic fit; winner documented with Brier score                                                                                                                            | _pending_ |         |          |             |        |
| Rating mapping matches D-1.5                            | Fixed, versioned thresholds; honesty caveat present in its documentation                                                                                                                   | _pending_ |         |          |             |        |
| Serving boundary matches D-1.6                          | No MLflow client dependency present in the serving container                                                                                                                               | _pending_ |         |          |             |        |
| Calibration check matches D-1.7                         | Standalone, unit-tested, importable function — not inline script logic                                                                                                                     | _pending_ |         |          |             |        |
| FastAPI schema matches D-1.8                            | Thin wrapper + canonical feature-list validator; no duplicated feature list                                                                                                                | _pending_ |         |          |             |        |
| `params.yaml` actually used                             | No hardcoded split ratio, seed, threshold, or hyperparameter found in source                                                                                                               | _pending_ |         |          |             |        |
| Exit criterion genuinely demonstrated — both directions | A deliberately miscalibrated candidate is blocked, **and** a well-calibrated model is correctly allowed through — a check that always blocks is as uninformative as one that always passes | _pending_ |         |          |             |        |

No row is marked "Resolved" from a description alone — each needs the actual file, metric, or test output checked before Phase 1 is signed off and Phase 2 starts.
