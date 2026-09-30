# Phase 1 — Staged Execution Plan

**Project:** ACRAS (Agentic Credit Risk & Analysis System)
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-09-28 · **Status:** Sequencing only — precondition satisfied (D-1.11 & D-1.12 approved), implementation ready to proceed · **Key References:** [Phase 1 Implementation Plan](../decisions/phase_1_implementation_plan.md) and [Technical Roadmap](../groundedness/technical_roadmap.md)

Same discipline as Phase 0's execution plan: nothing here is code, ADRs are assigned to the stage where the underlying fact actually gets built or verified, and falsification is applied selectively — where a stage's gate is a real programmatic check worth deliberately breaking once, not uniformly as a formality.

**Precondition status:** **Satisfied** — D-1.11 (Yeo-Johnson transform) and D-1.12 (no outlier removal) have been explicitly approved as recommended (Option B for both, logged in `phase_1_implementation_plan.md`). Stage 0 proceeds knowing these decisions are locked.

---

## Stage Index

| Stage | Name                                                         | Gate (one line)                                                                         | Falsification                                                   |
| ----- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| 0     | Pre-Implementation Verification & Dependency Check           | Every checklist item confirmed true                                                     |
| 1     | `params.yaml`, Canonical Feature List & Transform Definition | Feature list is 94 fields (post-D-1.10); transformer unit-tested in isolation           | Deferred — nothing to break yet against real data               |
| 2     | Feature Pipeline: Preprocessing & Split                      | Stratification holds; no train/test leakage in the fitted transformer                   | Yes                                                             |
| 3     | Model Training & Cross-Validated Calibration                 | All 12 configurations trained and logged; a winner identified by Brier score            | Yes — label-shuffle sanity check                                |
| 4     | Calibration Gate: Standalone Testable Function               | The gate function both passes a good synthetic case and blocks a bad one                | Yes — both directions, on synthetic data                        |
| 5     | Model Promotion, Freezing & Export                           | Real winning model passes the gate; a corrupted stand-in is blocked at promotion        | Yes — on the real artifact, not synthetic data                  |
| 6     | FastAPI Serving Layer                                        | Malformed requests rejected; valid requests scored correctly                            | Yes                                                             |
| 7     | Containerization                                             | Image builds; MLflow is verifiably absent from the runtime container                    | Yes                                                             |
| 8     | Endpoint & Pipeline Test Suite                               | Every prior stage's manual falsification now exists as a permanent automated test       | N/A — this stage formalizes 2–7's falsifications, adds none new |
| 9     | ADR Consolidation & Phase 1 Sign-Off                         | PIR fully populated; ADR-024–ADR-027 filed; exit criterion re-confirmed both directions | N/A — verifies documentation, not behavior                      |

---

## Stage 0 — Pre-Implementation Verification & Dependency Check ✅ **PASSED**

**Goal:** Confirm the ground truth every later stage assumes, before any pipeline code exists.

**Actions:**

- Confirm `lightgbm` (D-1.1/ADR-017) is added to `pyproject.toml` and installs cleanly via `uv sync`.
- Confirm the exact duplicate-column finding (D-1.10) against the live DVC-tracked dataset directly — check actual values match, not just trust the printed correlation coefficient.
- Decide whether `reports/eda/` outputs (the PNGs/CSVs from `explore_dataset.py`) are committed or gitignored-and-regenerable. Recommendation: gitignore the generated artifacts (they're reproducible on demand from the DVC-pinned dataset), commit the script itself — avoids bloating the repo with binary report images that duplicate what's already written into this plan's §6.
- Confirm MLflow tracking (`./mlruns`) is still functional from Phase 0's Stage 7 dummy run — a live check, not an assumption.
- Confirm `evidence_bundle.py`'s `pd`, `credit_rating`, `pd_band` fields are unchanged since Phase 0 sign-off.
- Verify the exact `scikit-learn` `CalibratedClassifierCV` API surface (parameter names, `cv` and `method` arguments) against the installed version — per the project's own 80%-confidence rule, confirmed rather than assumed, since D-1.2/ADR-018 depends on it directly.

**ADR Implements:** None — this stage produces verified facts and confirmations, not new decisions.

**Falsification:** Not applicable — every item is a manual confirmation with no programmatic failure mode to induce.

**Gate 0:** every item above confirmed true or logged as an exception with its own resolution.

---

## Stage 1 — `params.yaml`, Canonical Feature List & Transform Definition ✅ **PASSED**

**Goal:** Establish D-1.0's file and the single-source-of-truth feature list and transformer that every later stage — training, evaluation, and eventually the FastAPI validator — imports rather than redefines.

**Actions:**

- Create `params.yaml`: random seed, CV fold count (5, with the thin-fold-count caveat from §6 as a comment), calibration methods to fit (Platt and isotonic — both, per ADR-020), the PD-to-rating threshold table (D-1.5/ADR-021, with the illustrative-not-proprietary caveat as a comment), class-weighting flag (D-1.3/ADR-019).
- Create the canonical feature list (94 fields — 95 minus the duplicate dropped per D-1.10) as a single importable module/constant.
- Define the Yeo-Johnson transformer (D-1.11) as its own class/object; unit-test it in isolation against a handful of known-skewed EDA columns — not yet wired into the real training pipeline.

**ADR Implements:** **ADR-024** (D-1.10 — duplicate column resolution, folded into the canonical feature list's definition) and **ADR-025** (D-1.11 — Yeo-Johnson as the shared preprocessing transform).

**Falsification:** Deferred — the transformer's correctness (no leakage) can't be meaningfully falsified until it's fit against a real train/test split, which is Stage 2.

**Gate 1:** the canonical feature list has exactly 94 entries and excludes the dropped duplicate; the transformer's unit tests pass on the isolated known-skewed columns; `params.yaml` contains every value Stage 0–1's decisions fixed, with no magic numbers left in code.

---

## Stage 2 — Feature Pipeline: Preprocessing & Split ✅ **PASSED**

**Goal:** Build `src/pipelines/feature/` — the deterministic stage that turns the GX-validated raw dataset into model-ready data, honoring D-1.10, D-1.11, and D-1.12 together for the first time against real data.

**Actions:**

- Load the DVC-tracked dataset; apply the Stage 1 canonical feature list (drops the duplicate column).
- Perform the stratified train/test split — the test set is held out here and untouched until Stage 3's final evaluation; all CV happens only within the training portion (D-1.2/ADR-018).
- Fit the Yeo-Johnson transformer on the training portion only; persist the fitted transformer as an artifact.
- **Do not** apply IQR-based outlier removal or winsorization anywhere in this stage — D-1.12's decision is a deliberate absence, worth stating as an explicit non-action so it isn't quietly reintroduced later out of habit.

**ADR Implements:** **ADR-026** (D-1.12 — outlier handling: explicitly no removal/winsorization, tail values preserved for Tier 2/Tier 3's downstream use).

**Falsification:**

- Compute the positive-class ratio in the train split, the test split, and each of the 5 CV folds; confirm all match the overall 3.2% ratio within a tight tolerance — catches a non-stratified split immediately rather than after a full training run.
- Prove the transformer doesn't leak: refit it on the _full_ dataset (train+test combined) as a throwaway comparison, and confirm its parameters differ from the train-only fit — if they're identical, the "train-only" fit silently saw test data somewhere in the pipeline.

**Gate 2:** both falsifications pass; the persisted train/test artifacts and fitted transformer are present and versioned; the duplicate column is absent from the final feature set.

---

## Stage 3 — Model Training & Cross-Validated Calibration (Core) ✅ **PASSED**

**Goal:** Train XGBoost, LightGBM, and Logistic Regression (D-1.1/ADR-017), each weighted and unweighted (D-1.3/ADR-019), each calibrated with both Platt and isotonic (D-1.4/ADR-020) — 12 configurations total — and identify a winner by calibration first, discrimination second.

**Actions:**

- Train all 6 model×weighting configurations on the training portion.
- Apply 5-fold cross-validated calibration (D-1.2/ADR-018) with both methods to each, yielding 12 calibrated variants.
- Log every configuration's AUC/KS and Brier score/reliability curve to MLflow, tagged by model family, weighting, and calibration method for later filtering.
- Select the best configuration **by Brier score first** (the release-gate metric), using AUC only as a tiebreaker — this ordering is itself a stated policy, not an implicit assumption, consistent with INV-3's priority.

**ADR Implements:** None new — executes ADR-017 through ADR-020 as already decided. (The winning configuration itself is recorded in Stage 5, not here — training and comparing isn't yet promoting.)

**Falsification:** Train one additional, throwaway configuration on **randomly shuffled labels** and confirm its AUC lands near 0.5 (chance) and its calibration is trivially poor. If a label-shuffled model scored well, that would reveal a leakage bug somewhere upstream (Stage 2) that 12 legitimate-looking configurations could otherwise mask.

**Gate 3:** all 12 real configurations trained and logged with complete metrics; the label-shuffle sanity check confirms near-chance performance; a single winning configuration is identified and documented with its Brier score and AUC.

---

## Stage 4 — Calibration Gate: Standalone Testable Function 📌 **PENDING**

**Goal:** Extract the promotion check into an isolated, pure function per D-1.7 — not left as inline script logic — so Phase 5 can wire it into CI later without a refactor.

**Actions:**

- Implement `check_calibration(y_true, y_prob, brier_threshold)` and `check_discrimination(y_true, y_prob, auc_threshold)` (or one combined gate function) in a standalone module.
- Unit-test both against **synthetic, hand-constructed** arrays with known properties — a perfectly-calibrated synthetic case and a known-miscalibrated one — deliberately not using Stage 3's real model outputs for these tests, so the check itself is validated independently of any particular training run.

**ADR Implements:** None new — D-1.7 was already recorded as uncontested; this is where it's actually built.

**Falsification:** The one that matters most in this entire plan, and the direct answer to the PIR's own standing concern: feed the function a **deliberately well-calibrated** synthetic case and confirm it **passes**, then a **deliberately miscalibrated** one and confirm it **blocks**. A function that always blocks would trivially satisfy half of Phase 1's exit criterion while being useless — this falsification is what rules that out.

**Gate 4:** both directions of the synthetic falsification succeed; unit tests pass; the function is confirmed importable with no dependency on the training script itself.

---

## Stage 5 — Model Promotion, Freezing & Export 📌 **PENDING**

**Goal:** Run Stage 3's real winner through Stage 4's real gate, promote it, and export it per D-1.6/ADR-022.

**Actions:**

- Run the actual winning configuration through the Stage 4 gate function — this is the real, non-synthetic half of the exit criterion, complementing Stage 4's synthetic proof.
- Register the promoted model in the MLflow Model Registry (tracking/lineage only, per ADR-022).
- Export the frozen model as a `joblib` bundle **together with** the fitted Yeo-Johnson transformer — they must travel as one artifact to preserve training-serving parity.
- Implement the PD-to-rating mapping function (D-1.5/ADR-021) against the `params.yaml` threshold table; unit-test it specifically at the threshold boundaries (values exactly at a cutoff, values just above/below).

**ADR Implements:** **ADR-027** — records the actual promoted model, its configuration, and its Brier score/AUC, closing the "candidate set locked, winner pending" note left open by ADR-017.

**Falsification:** Substitute a **deliberately miscalibrated stand-in artifact** for the real winner and run the actual promotion step (not the isolated Stage 4 function) against it — confirm promotion is correctly blocked at the real integration point, not just in the unit-level check.

**Gate 5:** the real winner passes; the corrupted stand-in is blocked at the real promotion step; the exported bundle round-trips correctly (reload it, confirm predictions match pre-export); ADR-027 filed with real metrics.

---

## Stage 6 — FastAPI Serving Layer 📌 **PENDING**

**Goal:** Build `tier1_ml`'s service per ADR-010's boundary and D-1.8/ADR-023's schema.

**Actions:**

- Implement the thin request schema (`company_id`, `raw_features: dict[str, float | int]`) with a runtime validator against the Stage 1 canonical (94-field) feature list.
- Implement the response schema aligned to the evidence bundle's `pd`/`credit_rating` fields.
- Load the Stage 5 joblib bundle at startup; apply the same Yeo-Johnson transform to incoming requests that Stage 2 applied at training time — explicit training-serving parity, not assumed.
- Wire in the Stage 5 rating-mapping function.
- Confirm zero MLflow import anywhere in `tier1_ml`'s runtime code path.

**ADR Implements:** None new — executes ADR-010, ADR-022, ADR-023.

**Falsification:** Two probes: (1) a request missing a required feature key — confirm a clear validation error, not a silent NaN or a raw model exception; (2) a request with an unexpected extra key — confirm it's rejected (`extra="forbid"`-consistent with the evidence bundle's own convention), not silently ignored.

**Gate 6:** both malformed-request probes correctly rejected; a valid request returns a schema-correct PD and rating.

---

## Stage 7 — Containerization 📌 **PENDING**

**Goal:** Package `tier1_ml` as the lean serving image D-1.6/ADR-022 specifies.

**Actions:**

- Extend the Phase 0 `Dockerfile` (or add a Tier-1-specific build target) with the FastAPI service and its joblib bundle.
- Confirm the final image excludes training-only dependencies (MLflow client, Great Expectations, DVC) — only what `tier1_ml` itself needs to serve requests.

**ADR Implements:** None new.

**Falsification:** Build the image, open a shell inside the running container, and deliberately attempt `import mlflow` — confirm it fails with `ModuleNotFoundError`. This is a direct proof of ADR-022's boundary; a stray transitive dependency could otherwise sneak MLflow into the image without showing up in a casual read of `pyproject.toml`.

**Gate 7:** image builds; the deliberate `import mlflow` fails as expected; a live request against the _containerized_ service (not a local dev run) returns a correct response.

---

## Stage 8 — Endpoint & Pipeline Test Suite 📌 **PENDING**

**Goal:** Formalize every falsification performed by hand in Stages 2–7 into a permanent, automated suite (D-1.9).

**Actions:**

- Unit tests: the calibration-gate function (Stage 4), the rating-mapping function (Stage 5), the canonical-feature-list validator (Stage 1/6).
- Integration tests: the FastAPI endpoint (ideally containerized), covering Stage 6's valid and malformed-payload cases as permanent tests, not one-off manual probes.
- Regression test: Stage 3's label-shuffle sanity check, kept running permanently as an ongoing leakage guard — too valuable to discard once Stage 3 closes.

**ADR Implements:** None new.

**Falsification:** Not applicable as a separate step — this stage's entire content _is_ the formalization of Stages 2–7's falsifications into permanent tests. There's no new mutation to introduce that those stages haven't already covered by hand.

**Gate 8:** the full suite (`uv run pytest`) runs green; every falsification from Stages 2–7 now exists as a named, automated test — not a memory of having once checked it manually.

---

## Stage 9 — ADR Consolidation & Phase 1 Sign-Off 📌 **PENDING**

**Goal:** Close the loop between decided, built, and recorded — the same discipline as Phase 0's own Stage 9.

**Actions:**

- Confirm ADR-024 through ADR-027 are correctly filed in `system_design.md`.
- Update the Open Implementation Notes line currently reading "partially resolved by ADR-017" — now fully resolved; point it to ADR-027 instead.
- Update `system_design.md`'s status table: Phase 1 → its actual, honestly-reported outcome.
- Fill in every row of `phase_1_implementation_plan.md`'s Post-Implementation Review table (§7) — including the D-1.10/D-1.11/D-1.12 rows added during the EDA reassessment — with real values, not descriptions.
- Independently re-run the Roadmap's Phase 1 exit criterion **both directions** (a miscalibrated candidate blocked, a well-calibrated one allowed through) one final time, separate from Stage 4/5's proofs, to catch anything that regressed since.

**ADR Implements:** None new — this stage verifies the ledger is complete, it doesn't add to it.

**Falsification:** Not applicable — same reasoning as Phase 0's Stage 9: this checks documentation completeness against reality, not system behavior.

**Gate 9 (Phase 1 complete; Phase 2 may begin):** every PIR row populated with a real finding and no unresolved severity; `system_design.md` reflects reality; ADR-024 through ADR-027 filed and cross-referenced; the final both-directions exit-criterion re-run holds.
