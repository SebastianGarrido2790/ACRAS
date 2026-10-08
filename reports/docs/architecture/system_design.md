# System Design — Architectural Decision Record

**Project:** ACRAS (Agentic Credit Risk & Analysis System)
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-28 (Phase 0 closed: 2026-09-21, Phase 1 closed: 2026-10-02, Phase 2 closed: 2026-10-08) · **Status:** Phase 0, Phase 1 & Phase 2 complete

> This document reflects the **actual implemented state** of the system. At Phase 0, that state is "not yet built" — every component and diagram below is a planning-stage placeholder, explicitly marked as such, not a description of working code. It is updated at the close of each roadmap phase per the Update Protocol in §8; nothing here should be read as "done" until a phase's exit criteria have actually been demonstrated.

---

## Document Overview

- **What it is:** The primary System Design specification and Architectural Decision Record (ADR) detailing system topology, data flow, component interfaces, evidence-bundle contracts, and formal architectural decisions (ADR-001 through ADR-033).
- **Why it exists:** Codifies the immutable architectural boundaries (deterministic ML/simulation core vs. non-deterministic LLM reasoning layer), maintains a living record of implementation progress, and preserves technical decision rationale.
- **How to use it:** Refer to this document during component design and integration to adhere to architectural boundaries and interface schemas; update the status table and architecture specifications at the close of each development phase per the Update Protocol (§8).

---

## 1. Architecture Overview

ACRAS is a three-tier decision-support system built on one non-negotiable boundary: **Tiers 1 and 2 are deterministic and versioned; Tier 3 is the only layer where non-deterministic (LLM) reasoning is permitted.** A single typed evidence-bundle contract is the sole channel through which information crosses tier boundaries — no tier reads another tier's internal state directly, and no LLM output is allowed to become an input to a deterministic calculation. Tier 1 produces a calibrated probability of default; Tier 2 expands that into a risk distribution; Tier 3 fans out to three independently-mandated persona agents that interpret the same evidence in parallel and converge (or explicitly diverge) into one executive report.

## 2. Current Implementation Status

| Component                                                 | Status       | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| --------------------------------------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Planning docs (Scoping, PRD, User Story, Roadmap) | **Complete** | This ADR is the next artifact in that sequence.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Phase 0 — Scaffolding & data contracts                    | **Complete** | Closed 2026-09-21. Deliverables: uv-managed env (Python 3.12), Docker base image (`python:3.12-slim`), DVC-tracked dataset (6,819 × 96, SHA-256 pinned, local filesystem remote, ADR-012), GX 1.21 data contract (ADR-013), pre-v0 evidence-bundle schema (ADR-014), MLflow tracking wired, CI (Ruff + Pyright + module-size + 15-test suite, ADR-015). Docker CI verified green on Actions run #5 (a47709a), 2026-09-24. Exit criterion demonstrated: corrupted fixture halts pipeline; falsification confirms test sensitivity. ADR-010 through ADR-015 all filed. |
| Phase 1 — Tier 1 ML core                                  | **Complete** | Closed 2026-10-02. Deliverables: deterministic feature pipeline (Yeo-Johnson transform fit strictly on train split, exact duplicate dropped per ADR-024, zero outlier removal per ADR-026); 12 candidate configurations trained, calibrated (5-fold CV Platt & Isotonic), and logged to MLflow; winning XGBoost unweighted isotonic model promoted (Brier=0.020766, AUC=0.959496, KS=0.793182, ADR-027); standalone promotion gate function (INV-3 / FR12); PD-to-rating mapping module (ADR-021); FastAPI serving layer (ADR-023) with zero MLflow dependency (ADR-022); hardened multi-stage Docker serving image; 53 automated unit/integration tests green. Exit criterion demonstrated in both directions. |
| Phase 2 — Tier 2 Monte Carlo                              | **Complete** | Closed 2026-10-08. Deliverables: typed simulation config and benchmark gate (ADR-028, ADR-030); vectorized Monte Carlo engine with deterministic seeded output, Cholesky correlated macro shocks, and strict percentile monotonicity (ADR-029); deterministic financial ratio extractor with zero-division safety clamps (ADR-033); decoupled in-memory orchestration service (ADR-031); EvidenceBundle schema v1 migration enforcing non-null Tier 1 and Tier 2 outputs (ADR-032); sub-5ms latency regression benchmark ($P_{95}=1.20\text{ ms}$ core engine, $P_{95}=2.88\text{ ms}$ full in-memory pipeline); and comprehensive 81-test automated suite green. Phase 2 exit criteria demonstrated in both directions. ADR-028 through ADR-033 all filed. |
| Phase 3 — LLM gateway & circuit breaker                   | Not started  | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Phase 4 — Tier 3 multi-agent core                         | Not started  | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Phase 5 — Evaluation harness & governance gates           | Not started  | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Phase 6 — Dashboard & trace logging                       | Not started  | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Phase 7 — Integration & doc close-out                     | Not started  | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

This table is the authoritative "what actually exists" record. It is the first thing updated at the close of each phase — see §8.

## 3. High-Level Architecture Diagram

_(Planned — no implementation exists yet)_

```
                         ┌─────────────────────────┐
                         │     Company Profile      │
                         │   (dashboard / API in)   │
                         └────────────┬─────────────┘
                                      ▼
                    ┌──────────────────────────────────┐
                    │  TIER 1 — Frozen ML Core (det.)   │
                    │  FastAPI-served PD model          │
                    └────────────────┬───────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │  TIER 2 — Monte Carlo Engine (det.)│
                    │  P10 / P50 / P90 risk distribution │
                    └────────────────┬───────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │      Evidence Bundle (typed)      │
                    │  PD + MC bands + financial ratios │
                    └───────────────┬────────────────────┘
                                    ▼
        ┌───────────────────────────────────────────────────────┐
        │        LLM GATEWAY (circuit breaker + fallback)        │
        └───────────────┬───────────────┬───────────────┬────────┘
                         ▼               ▼               ▼
                 ┌──────────┐    ┌──────────────┐  ┌───────────┐
                 │   CRO    │    │    Growth     │  │  Capital  │
                 │  Persona │    │    Persona    │  │  Persona  │
                 └────┬─────┘    └───────┬───────┘  └─────┬─────┘
                      └──────────────┬───┴────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │   Convergence Node (deterministic  │
                    │   divergence score, HITL branch)   │
                    └────────────────┬───────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │           Orchestrator            │
                    │      (final executive report)     │
                    └────────────────┬───────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │   Dashboard (Risk Manager view)   │
                    └──────────────────────────────────┘

     Side systems: GX data-contract gate → DVC pipeline (feeds Tier 1 training)
                   Golden dataset + calibration/divergence gates (feed CI, block promotion)
```

## 4. Component Descriptions

| Component                            | Planned Responsibility                                                                               | Status   |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------- | -------- |
| Tier 1 FastAPI service               | Serve the frozen, calibrated PD model                                                                | Complete |
| Tier 2 Monte Carlo module            | Convert Tier 1 output into P10/P50/P90 bands                                                         | Complete |
| Evidence-bundle schema               | Single typed contract shared by all tiers (v1 contract active)                                       | Complete |
| LLM Gateway                          | Custom, `pybreaker`-backed interface over Gemini (primary) and HF Inference API (fallback) — ADR-009 | Planned  |
| Circuit breaker                      | Halts calls to a failing provider, triggers fallback                                                 | Planned  |
| Data Scientist Agent                 | Calls Tier 1 endpoint, maps PD → credit rating                                                       | Planned  |
| Financial/Domain Analyst Agent       | Computes financial ratios from evidence bundle                                                       | Planned  |
| CRO / Growth / Capital persona nodes | Independent, rubric-conditioned interpretation, emit `PersonaVerdict`                                | Planned  |
| Convergence node                     | Deterministic divergence scoring + HITL escalation branch                                            | Planned  |
| Orchestrator                         | Aggregates all agent output into the executive report                                                | Planned  |
| Dashboard                            | Risk Manager–facing input/output interface                                                           | Planned  |
| GX/DVC pipeline                      | Data-contract gate in front of model training                                                        | Complete |
| Evaluation harness                   | Golden dataset, calibration gate, divergence gate, regression tests                                  | Planned  |

## 5. Data Flow

_(Planned sequence, referencing the evidence-bundle schema versions defined in the roadmap)_

1. A company profile (structured financials, requested loan terms, qualitative fields) enters via the dashboard or API.
2. Tier 1 returns a PD — evidence bundle reaches **schema v0**.
3. Tier 2 expands the PD into P10/P50/P90 bands — evidence bundle reaches **schema v1**.
4. The Data Scientist Agent and Financial/Domain Analyst Agent add the credit-rating mapping and computed ratios.
5. The completed evidence bundle is broadcast to the three persona nodes in parallel (fan-out) through the LLM Gateway; each returns a structured `PersonaVerdict` — evidence bundle reaches **schema v2**.
6. The convergence node computes a deterministic divergence score over the three verdicts and either finalizes or routes to HITL.
7. The Orchestrator assembles the final report; a full machine-readable trace (tool calls, fallback events, bands, verdicts, divergence score) is persisted alongside it.
8. The dashboard displays the report and, where applicable, the escalation state.

## 6. Architectural Decision Records

Each entry below is a decision already made during planning — accepted, not placeholder — even though the code that implements it doesn't exist yet.

**ADR-001 — Deterministic core / probabilistic shell boundary**
_Status:_ Accepted. _Context:_ ML models compute well but explain poorly; LLMs explain well but compute poorly. _Decision:_ Tiers 1–2 are fully deterministic and version-pinned; only Tier 3 may be non-deterministic. No LLM output is ever allowed to feed a deterministic calculation. _Consequences:_ every numeric claim in a report is traceable to a fixed calculation; LLM failure modes (hallucination) are structurally confined to the interpretation layer.

**ADR-002 — Shared evidence-bundle contract as the sole inter-tier channel**
_Status:_ Accepted. _Context:_ independent, differently-worded prompts per tier/agent would make it impossible to guarantee all reasoning is grounded in the same facts. _Decision:_ one Pydantic-validated evidence bundle is the only channel between tiers; no tier or agent receives ad hoc context outside it. _Consequences:_ enables meaningful divergence measurement in Tier 3, since all three personas are provably reading identical inputs.

**ADR-003 — Calibration as a first-class release gate**
_Status:_ Accepted. _Context:_ a model can rank risk well (high AUC) while being systematically miscalibrated, corrupting every downstream probability-dependent tier. _Decision:_ model promotion requires passing a calibration check (Brier score / reliability curve) in addition to discrimination metrics; AUC alone is insufficient (FR12). _Consequences:_ a well-ranked but miscalibrated model is blocked from serving, even if it would have looked acceptable under a discrimination-only review.

**ADR-004 — Deterministic divergence scoring via structured `PersonaVerdict`**
_Status:_ Accepted. _Context:_ scoring divergence via an LLM judge comparing narrative text would add a probabilistic measurement on top of a probabilistic output. _Decision:_ each persona emits a structured, validated verdict (`recommendation`, `lean`, `confidence`) alongside its narrative; divergence is a deterministic function over these fields. _Consequences:_ divergence scoring is unit-testable and reproducible; the threshold is calibrated against the golden set as a provisional, documented constant (see Roadmap Phase 5).

**ADR-005 — Uniform low temperature; divergence engineered structurally**
_Status:_ Accepted. _Context:_ using persona temperature to manufacture divergence would make Tier 3 outcomes nondeterministic on re-run, undermining auditability. _Decision:_ all three personas run at the same low temperature (~0–0.2); genuine divergence comes from role-conditioned rubrics and role-specific derived fields drawn from the same evidence bundle, not sampling randomness. _Consequences:_ a fixed-settings regression test (same case, same settings, twice) is expected to return the same recommendation category — any drift signals a defect, not intended behavior.

**ADR-006 — LLM Gateway with circuit breaker and cross-provider fallback**
_Status:_ Accepted. _Context:_ a single LLM provider's outage or rate limit would take down the entire interpretation tier. _Decision:_ all LLM calls route through a gateway with a circuit breaker (defined timeout/consecutive-error thresholds) and an automatic fallback to a secondary provider. _Consequences:_ provider diversity becomes a resilience property of the system rather than a manual failover procedure.

**ADR-007 — Great Expectations–gated DVC pipeline**
_Status:_ Accepted. _Context:_ a bad or drifted training dataset silently propagates into a bad model with no upstream signal. _Decision:_ Great Expectations checks the data contract before the DVC pipeline is allowed to proceed to training; a failed expectation halts the pipeline. _Consequences:_ garbage-in failures are caught at the data layer, not discovered later in model evaluation.

**ADR-008 — Domain-native persona framing (CRO / Growth / Capital)**
_Status:_ Accepted. _Context:_ lending economics has its own native three-way tension. _Decision:_ persona roles are named and mandated around risk exposure, growth appetite, and cost of capital — not a generic or borrowed labeling scheme. _Consequences:_ each persona's rubric (§ADR-005) has a domain-authentic reason to diverge, rather than an arbitrary one.

**ADR-009 — Custom `pybreaker`-backed LLM gateway; Hugging Face Inference API as secondary provider**
_Status:_ Accepted. _Context:_ ADR-006 established that all LLM calls must route through a gateway with a circuit breaker and cross-provider fallback, but left the gateway implementation (custom vs. off-the-shelf) and the specific secondary provider open, pending comparative evaluation. _Decision:_ build a custom gateway with a thin provider-routing interface, backed by `pybreaker` for the circuit-breaker state machine (closed/open/half-open) rather than adopting a general-purpose multi-provider library (e.g., LiteLLM) wholesale. Gemini remains the primary provider. Hugging Face Inference API is the secondary/fallback provider, targeting a small-to-mid instruction-tuned open model — candidate: Llama-3.1-8B-Instruct or Mistral-7B-Instruct-v0.3. _Consequences:_ the resilience mechanism stays small enough (~50–80 lines beyond the `pybreaker` primitive) to fully read, test, and explain, consistent with the project's preference for owned, provable mechanisms over imported ones (see ADR-001's rationale). The fallback path is free-tier compatible, which matters because the evaluation harness (Roadmap Phase 5) re-runs the golden set repeatedly and shouldn't incur real cost on every CI run. Trade-off accepted: no access to LiteLLM's broader provider catalog or community maintenance — acceptable since ACRAS's provider set is fixed at two, not expected to grow. **Not yet resolved by this ADR:** the exact HF model is a shortlist, not a final pin — free-tier model availability on HF's Inference API changes over time and was not independently verified as of this ADR's date; confirm and pin at Phase 3 implementation time (carried forward to §7 below).

**ADR-010 — Structural separation of training and serving (`pipelines/training/` vs. `src/tier1_ml/`)**
_Status:_ Accepted. _Context:_ Latent finding #2 in the Phase 0 audit identified that having both a training pipeline and a model module without a strict boundary risks overlapping responsibilities or runtime training leakage. _Decision:_ `pipelines/training/` produces, calibrates, and registers the frozen model artifact (the FTI training stage); `src/tier1_ml/` contains strictly the FastAPI serving microservice and thin inference wrapper around registered artifacts. Serving code never implements or executes training logic; it only loads a frozen, registered artifact. _Consequences:_ Clean separation of concerns between model development and serving infrastructure; serving runtime is completely decoupled from training dependencies and data-contract pipelines; directly enforces INV-1.

**ADR-011 — Public dataset pin and entity-type caveat (Kaggle Company Bankruptcy Prediction)**
_Status:_ Accepted. _Context:_ ACRAS requires a real, tabular corporate bankruptcy dataset to ground the Phase 0 data contracts and Tier 1 probability of default model. D-0.1 evaluated candidates and selected the Taiwan Economic Journal bankruptcy dataset via Kaggle. _Decision:_ pin the dataset to the verified snapshot containing 6,819 rows × 96 columns (dataset SHA-256: `67BF2E7C75490F7AD3F76BBCE57D49CDC25967CDAB607527B94F944863FA14D8`, DVC tracked MD5: `da9cda1b8f7cb99d03fbb65b86c15b0f`). _Consequences:_ provides stable, deterministic data contracts for Great Expectations and reproducible feature engineering. Entity-type caveat acknowledged: the dataset is derived from Taiwanese stock-exchange-listed companies rather than unlisted SMEs; this proxy limitation is acceptable for system architecture, calibration gates, and multi-agent pipeline validation, with SME-specific adjustments noted for future data ingestion.

**ADR-012 — DVC remote storage backend: local filesystem remote outside repository (superseding S3)**
_Status:_ Accepted (Supersedes preliminary AWS S3 decision in D-0.3). _Context:_ initial planning in D-0.3 favored AWS S3 to demonstrate cloud credential handling. However, without an active AWS account, provisioning an S3 bucket blocked Gate 3. Alternative cloud options like Google Drive introduce OAuth friction and API rate limits. DVC's fundamental reproducibility requirement is that the remote storage is distinct and isolated from the working copy. _Decision:_ configure DVC with a default local filesystem remote located in a dedicated directory outside the repository root (e.g., `../acras_dvc_remote`). _Consequences:_ satisfies DVC's reproducibility and fresh-clone pull contract with zero external cloud dependencies or account costs; eliminates OAuth token maintenance; provides complete file isolation between the active Git workspace and the data version store. If a cloud backend is needed in future deployment stages, DVC remote configuration can be switched without modifying pipeline definitions or data hashes.

**ADR-013 — Great Expectations API generation (GX 1.21 Core) & data contract scope**
_Status:_ Accepted. _Context:_ D-0.5a tentatively suggested the legacy Validator API but mandated implementation-time verification of the active release. Verification established that `great-expectations 1.21.0` is installed. In GX 1.x, the legacy Validator API is superseded by typed expectation classes (`great_expectations.expectations.core`). D-0.5b required resolving expectation scope to minimal, real coverage. _Decision:_ standardize on GX 1.21 Core API with typed expectation objects (`gxe.Expect...`) and declarative JSON suite persistence (`gx/expectations/bankruptcy_data_suite.json`), implemented in `src/pipelines/data_contracts.py`. Scope is strictly pinned to table schema (96 columns, 6,000–7,500 rows), target integrity (`Bankrupt?` in `{0, 1}` with 0% nulls), binary categorical flags, 0% nulls and `[0.0, 1.0]` bounded ranges across 11 core financial ratios (covering Profitability, Leverage/Solvency, Liquidity, and Coverage pillars), and compound column uniqueness across key ratios. Statistical distribution-drift and anomaly detection are explicitly deferred to Phase 5 production monitoring. _Consequences:_ establishes a deterministic, fast-executing data contract gating the DVC pipeline (INV-7); prevents scope creep into monitoring while guaranteeing that corrupted schema, null spikes, or out-of-bounds financial indicators halt training immediately.

**ADR-014 — Evidence-bundle schema versioning resolution & pre-v0 draft scope**
_Status:_ Accepted. _Context:_ Latent finding #1 from the Phase 0 audit noted an ambiguity in evidence-bundle version numbering (whether Phase 0 produces "v0" or a draft). D-0.6 evaluated renumbering existing documents vs. preserving them. _Decision:_ preserve existing documentation unchanged and formally define that Phase 0 delivers a **pre-v0 draft skeleton** (`schema_version = "pre-v0-draft"`). Formal schema versioning begins at Tier 1 ML serving (`v0` with calibrated PD), advancing at Tier 2 (`v1` with Monte Carlo percentiles), and Tier 3 (`v2` with persona verdicts). Implement the pre-v0 skeleton in `src/schemas/evidence_bundle.py` with strongly-typed sub-models (`PDBand`, `PersonaVerdict`), requiring `company_id` and verified `raw_features`, with downstream tier fields defaulting to `None`. Enforce strict immutability and schema compliance via `ConfigDict(extra="forbid", frozen=True)`. _Consequences:_ preserves architectural documentation integrity without cosmetic version renumbering sweeps; locks structural boundaries in Python code with zero ad hoc context leakage (INV-2); ensures compile-time type safety across all future tier boundaries from Day 1.

**ADR-015 — CI skeleton scope for Phase 0 (confirming D-0.7 deferral)**
_Status:_ Accepted. _Context:_ D-0.7 evaluated the scope of continuous integration for Phase 0, contrasting a lightweight verification workflow against building full `dvc repro`-in-CI with cloud remote storage credentials. _Decision:_ scope Phase 0 GitHub Actions CI (`.github/workflows/ci.yml`) to fast, deterministic checks: code formatting and linting (Ruff), static type checking (Pyright), module size enforcement (`scripts/check_module_size.py`), full automated test suite execution (including in-repo fixture-based adversarial gate tests), and container build verification (`Dockerfile`). Full `dvc repro`-in-CI remote access plumbing is explicitly deferred to Phase 5 alongside the calibration and divergence gate CI integration. _Consequences:_ guarantees that every push and PR is automatically verified against code quality, type safety, and gate invariants within 2–3 minutes; avoids duplicate setup of CI cloud remote credentials; delivers a reproducible, hermetic testing baseline across clean remote runners.

**Note on ADR-016:** reserved, not skipped. §7 below already earmarks ADR-016 specifically for the deferred Tier 3 evidence-bundle fields when Phase 4 begins — it is deliberately left open here rather than consumed by the Phase 1 decisions below, so that forward pointer stays accurate rather than becoming stale documentation drift.

**ADR-017 — Model candidate set: XGBoost, LightGBM, and a Logistic Regression baseline (D-1.1)**
_Status:_ Accepted. _Context:_ the Roadmap named XGBoost and LightGBM as Phase 1 candidates. D-1.1 evaluated whether to also include a naturally-calibrated baseline, given calibration (INV-3) is a first-class release gate, not merely a discrimination metric to report. _Decision:_ train and compare three candidates — XGBoost, LightGBM, and Logistic Regression. LightGBM is added as a new `pyproject.toml` dependency (previously absent despite being named in the Roadmap). _Consequences:_ the Logistic Regression baseline's near-native calibration provides a diagnostic reference point for measuring how much distortion the boosted-tree candidates introduce, directly informing ADR-020's calibration-method selection; adds one more model to track in MLflow at negligible marginal training cost given the dataset's size. **Not yet resolved by this ADR:** which of the three ultimately wins and is promoted is a Phase 1 EDA/training outcome, not decided here — this ADR fixes the candidate _set_, not the final choice (see §7).

**ADR-018 — Data-splitting & calibration strategy: cross-validated calibration over a naive three-way split (D-1.2)**
_Status:_ Accepted. _Context:_ the dataset (6,819 rows, ADR-011) has a known small positive (bankrupt) class. D-1.2 evaluated a naive stratified train/calibration/test split against cross-validated calibration, given the statistical risk of an under-populated minority class in any single held-out slice. _Decision:_ use cross-validated calibration (`CalibratedClassifierCV`-style, e.g., 5-fold) fit on the training data, with a separate, stratified held-out test set reserved only for final evaluation; every split and fold is stratified by the target label. _Consequences:_ makes efficient use of scarce positive-class examples across folds rather than permanently sequestering a portion of them into one calibration slice; adds fold-management complexity relative to a naive split, accepted as necessary given the dataset's size and calibration's weight as a release gate.

**ADR-019 — Class-imbalance handling: class weighting over resampling (D-1.3)**
_Status:_ Accepted. _Context:_ D-1.3 evaluated class weighting, oversampling (SMOTE), undersampling, and no adjustment, against the dataset's known imbalance and the project's calibration priority (INV-3). _Decision:_ use class weighting (`scale_pos_weight` for XGBoost/LightGBM, `class_weight="balanced"` for Logistic Regression) as the primary approach, trained and compared against an unweighted baseline — no synthetic resampling. _Consequences:_ preserves the true population base rate in the training data, which resampling would distort and require additional correction to keep calibration valid; the unweighted baseline is retained as an empirical check, not an assumption that weighting is strictly necessary.

**ADR-020 — Post-hoc calibration method: fit both Platt and isotonic, select empirically per model (D-1.4)**
_Status:_ Accepted. _Context:_ D-1.4 evaluated Platt scaling and isotonic regression as post-hoc calibration methods, anticipated in Runbook entry #2 for correcting a miscalibrated raw model. _Decision:_ fit both methods on the calibration folds for each candidate model; select and document whichever achieves the better (lower) held-out Brier score, per model. _Consequences:_ replaces an a priori methodological guess with a measured, per-model empirical answer at negligible additional compute cost; the selected method and its Brier-score comparison must be recorded in the calibration report deliverable for auditability.

**ADR-021 — PD-to-credit-rating mapping: fixed illustrative thresholds, not data-driven bucketing (D-1.5)**
_Status:_ Accepted. _Context:_ PRD FR4 requires converting a calibrated PD into a credit-rating category. D-1.5 evaluated fixed, industry-convention-inspired PD thresholds against data-driven quantile bucketing off the training set's own PD distribution. _Decision:_ adopt a fixed, versioned PD-threshold table (illustrative bands loosely inspired by public rating-agency convention) stored in `params.yaml` or a dedicated config module — never as inline magic numbers, never re-derived per training run. _Consequences:_ preserves external legibility of the rating output across retraining, since the mapping doesn't shift with each new run's PD distribution (the documented weakness of the rejected alternative). Documentation of this mapping must state plainly that the thresholds are illustrative and not a verified or licensed reproduction of any specific rating agency's proprietary methodology — a stated caveat, not an implicit assumption.

**ADR-022 — Model serialization & serving boundary: MLflow for tracking, lean `joblib` export for serving (D-1.6)**
_Status:_ Accepted. _Context:_ D-1.6 evaluated whether `tier1_ml`'s FastAPI service should load the promoted model directly from the MLflow Model Registry at runtime, or from a lean exported artifact, given ADR-010's boundary that `tier1_ml` is strictly a serving module. _Decision:_ use MLflow for experiment tracking and model registry during training only. At promotion, export the frozen model as a `joblib` artifact; `tier1_ml` loads this artifact directly at startup, with zero MLflow client dependency in the serving container. _Consequences:_ keeps the serving container's dependency footprint, image size, and cold-start time minimal, consistent with ADR-010's scope for `tier1_ml`; requires an explicit export/promotion step in the training pipeline to produce the `joblib` artifact from the registered MLflow model.

**ADR-023 — FastAPI inference schema: thin wrapper with canonical feature-list validation (D-1.8)**
_Status:_ Accepted. _Context:_ GX (ADR-013) validates the training-time data contract only; it provides no protection for the live FastAPI inference endpoint against a malformed request. D-1.8 evaluated a fully-expanded ~95-field Pydantic request model against a thin wrapper with runtime key validation against one canonical feature list. _Decision:_ the inference request schema is a thin wrapper (`company_id: str`, `raw_features: dict[str, float | int]`), matching the evidence bundle's own shape, with a runtime validator checking `raw_features`'s keys against a single canonical feature list imported by both the training pipeline and the serving module — never duplicated as ~95 individually hand-maintained Pydantic fields. _Consequences:_ closes the inference-time validation gap GX's training-only scope leaves open, without introducing a second, independently-maintained feature list that could drift out of sync with the training pipeline's actual feature set — a drift risk this project has repeatedly guarded against elsewhere (dataset naming, schema versioning, enum spelling).


**ADR-024 — Duplicate feature column resolution: drop exact duplicate `Current Liability to Liability` (D-1.10)**
_Status:_ Accepted. _Context:_ EDA revealed that `Current Liability to Liability` and `Current Liabilities/Liability` are perfectly collinear (Pearson r = 1.000). Direct element-by-element verification across all 6,819 rows confirmed maximum absolute difference is 0.0 (exact duplicate values stored under two distinct header names). _Decision:_ drop `Current Liability to Liability` and retain `Current Liabilities/Liability` in the canonical feature list (bringing canonical features to exactly 94). Retaining `Current Liabilities/Liability` preserves alignment with the "/" naming convention of the dataset's other ratio features (`Quick Assets/Total Assets`, `Cash/Total Assets`). The dropped column is permanently excluded from the canonical feature list (`src/schemas/features.py`), ensuring both training and inference validation reject this redundant column. _Consequences:_ eliminates exact multicollinearity at the feature contract boundary; modifies the expected feature count for D-1.8/ADR-023's inference schema from 95 to 94.

**ADR-025 — Continuous feature preprocessing: shared Yeo-Johnson power transformation (D-1.11)**
_Status:_ Accepted. _Context:_ EDA demonstrated that 73 of the 95 raw continuous features exhibit severe skewness (|skew| > 2.0). D-1.11 evaluated unscaled raw inputs, dual preprocessing pipelines, and a single shared Yeo-Johnson power transformation feeding all three candidate models. _Decision:_ apply a Yeo-Johnson power transformation (`sklearn.preprocessing.PowerTransformer(method="yeo-johnson", standardize=True)`) as the single, shared preprocessing step for continuous features across all models. Box-Cox and standard log transformations were rejected because several financial ratios (e.g. net growth rates) take negative or zero values, which Yeo-Johnson natively handles. Tree models (XGBoost, LightGBM) are invariant to monotonic transformations of individual features, while the Logistic Regression baseline critically requires skew compression and scaling to provide a meaningful calibration diagnostic. _Consequences:_ avoids pipeline divergence and training-serving skew by sharing a single fitted transformation object; requires serializing the fitted `YeoJohnsonTransformer` alongside the trained model bundle at promotion (ADR-022) to guarantee identical transformations during inference.

**ADR-026 — Outlier handling: explicitly no removal or winsorization (D-1.12)**
_Status:_ Accepted. _Context:_ EDA revealed that 71 of the 95 raw features exceed 5% outliers under the IQR×1.5 heuristic, with severe skewness in several ratios (e.g. Degree of Financial Leverage reaching 22% outliers). D-1.12 evaluated standard IQR-based outlier pruning or winsorization against retaining all observed values untouched. _Decision:_ explicitly do not remove or winsorize outliers. Extreme financial ratios (e.g., highly compressed interest coverage, extreme leverage) represent genuine distressed SME risk signals rather than data measurement corruption. Retaining these records preserves the tail-risk signal that downstream components — Tier 2 Monte Carlo P90 loss distribution and Tier 3 CRO persona tail-loss interpretation — are explicitly designed to evaluate. Skew compression for the linear baseline is achieved monotonically via Yeo-Johnson transformation (ADR-025) without deleting critical default observations. _Consequences:_ prevents deleting true distressed-firm default signal; guarantees the 100% data retention invariant for Tier 2 and Tier 3 inputs.

**ADR-027 — Tier 1 Promoted Model Selection: XGBoost (Unweighted, Isotonic Calibration) (D-1.6 / D-1.7)**
_Status:_ Accepted. _Context:_ ADR-017 established the three candidate model families (XGBoost, LightGBM, Logistic Regression) with the final selection explicitly deferred to Phase 1 empirical evaluation against the dual promotion gate (INV-3 / PRD FR12: calibration check first, discrimination check second). D-1.3 evaluated class weighting vs. unweighted empirical loss, and D-1.4 evaluated Platt scaling vs. isotonic regression. _Decision:_ promote XGBoost trained on unweighted empirical cross-entropy loss and calibrated via 5-fold cross-validated Isotonic regression as the frozen Tier 1 model for serving. On the held-out test split (1,364 rows, 44 defaults), this configuration achieved:
- Brier score: **0.020766** (ranked #1 of 12 candidate configurations, comfortably surpassing the $\le 0.030$ release threshold).
- ROC-AUC: **0.959496** (surpassing the $\ge 0.850$ release threshold).
- KS Statistic: **0.793182**.
The promoted model is registered in MLflow (`acras-tier1-pd-model`) for lineage tracking and exported together with the fitted `YeoJohnsonTransformer` as a lean `joblib` bundle (`artifacts/promoted_model_bundle.joblib`) for serving with zero MLflow dependency in the inference container (ADR-022). This decision resolves and closes the open note left by ADR-017. _Consequences:_ Locks XGBoost (unweighted, isotonic) as the deterministic PD engine powering Tiers 1 and 2; guarantees training-serving parity by bundling the preprocessor with the model; satisfies the Roadmap Phase 1 model deliverable.

**ADR-028 — Simulation Configuration & Reproducibility Parameters (D-2.0)**
_Status:_ Accepted. _Context:_ Phase 2 begins by turning the Monte Carlo design into a versioned, traceable configuration contract rather than a set of inline magic numbers spread across the engine. D-2.0 required codifying the simulation hyperparameters in `params.yaml` and validating them before they reach the simulation logic. _Decision:_ define a strict `SimulationConfig` model in `src/config/loader.py` with immutable, explicit bounds (`n_iterations`, `seed`, `asset_correlation`, per-percentile tolerances, `latency_budget_ms`, `macro_volatility`, `debt_service_shock_std`, `asset_haircut_std`) and forbid unrecognized keys via `ConfigDict(extra="forbid", frozen=True)`. Integrate it into the root `AppConfig` / `ProjectParams` model and expose the validated object through `load_params()`. The active configuration in `params.yaml` is:
- `n_iterations: 10000`
- `seed: 42`
- `asset_correlation: 0.15`
- `tolerance_p10: 0.015`
- `tolerance_p50: 0.015`
- `tolerance_p90: 0.020`
- `latency_budget_ms: 5.0`
- `macro_volatility: 0.20`
- `debt_service_shock_std: 0.15`
- `asset_haircut_std: 0.10`
_Consequences:_ the Tier 2 engine no longer relies on unvalidated magic numbers, and invalid simulation parameters fail immediately with a `pydantic.ValidationError` instead of silently misconfiguring the Monte Carlo engine. This creates a deterministic, reviewable configuration boundary for every Phase 2 and Phase 3 simulation run, and aligns the project with the invariant that external configuration is untrusted until validated.

**ADR-029 — Unified Vasicek Structural & Correlated Macro-Shock Engine (D-2.1, D-2.1a, D-2.1b)**
_Status:_ Accepted. _Context:_ D-2.1 evaluated the Monte Carlo engine design against a naive one-factor simulation, a full joint-factor simulation, and the selected hybrid approach that preserves the structural PD default condition while modeling correlated macro and balance-sheet shocks. _Decision:_ implement a pure vectorized NumPy engine that forms a 3-variable correlated Gaussian system (macro shock, debt-service shock, collateral haircut), applies the Cholesky decomposition of the correlation matrix, generates correlated standard-normal draws, and maps the result through the Vasicek structural default condition `Z_i < Phi^-1(PD)`. Empirical percentiles are computed with `np.percentile(..., method="weibull")` and strictly monotonicity-checked for `p10 <= p50 <= p90` and bounds in `[0, 1]`. _Consequences:_ yields a deterministic, reproducible engine under a fixed seed and a mathematically valid structure for benchmarking against the analytic Vasicek quantile formula; also establishes the invariant that malformed correlation matrices are rejected before they can silently poison the simulation.

**ADR-030 — Closed-Form Vasicek Analytical Verification Benchmark (D-2.2)**
_Status:_ Accepted. _Context:_ the Monte Carlo engine must be validated against a mathematically exact reference and a tolerance gate, not against itself. D-2.2 evaluated the viability of an in-sample empirical benchmark against a closed-form analytical formula and selected the latter because it is deterministic, pure, and ideal for both pass/fail gating and code auditability. _Decision:_ implement the benchmark in `src/tier2_simulation/benchmark.py` using SciPy's `norm.ppf` and `norm.cdf` to evaluate the exact expression
$$q_{\alpha} = \Phi\left(\frac{\Phi^{-1}(p) + \sqrt{\rho}\,\Phi^{-1}(\alpha)}{\sqrt{1-\rho}}\right)$$
for the 10th, 50th, and 90th percentiles, plus `vasicek_pdf` and `vasicek_cdf` helpers and a `verify_simulation_benchmark` gate that computes absolute deltas against the analytical values and enforces the configured tolerances. _Consequences:_ the benchmark acts as the truth source for Tier 2 validation; a valid analytical band passes cleanly while deliberately perturbed values are rejected with explicit delta reporting, preventing silent acceptance of a miscalibrated or corrupted Monte Carlo band. This keeps the downstream Monte Carlo engine and its tolerance logic auditable and testable in both directions.

**ADR-031 — Tier 1/Tier 2 In-Memory Decoupled Integration Pattern (D-2.3)**
_Status:_ Accepted. _Context:_ Tier 2 requires the calibrated probability of default produced by Tier 1 to generate its risk distribution and financial ratios. D-2.3 evaluated connecting the tiers via an HTTP microservice call versus a direct in-memory function or service consumer (`src/tier2_simulation/service.py`). _Decision:_ adopt Option B (Direct In-Memory Function / Service Consumer), running the Tier 1 → Tier 2 pipeline via `run_simulation_pipeline` or `Tier2SimulationService` without network overhead or model-retraining coupling, while strictly validating Tier 1 inputs (`pd`, `credit_rating`, `raw_features`) and halting with `InvalidTier1InputError` before any matrix calculations. _Consequences:_ preserves the sub-5ms total latency budget, eliminates localhost HTTP management overhead during test execution, ensures 100% testability, and strictly complies with the deterministic core invariants (INV-1, INV-2) and the separation of training and serving (ADR-010).


**ADR-032 — EvidenceBundle Schema v1 Migration & PDBand Enforcement (D-2.4)**
_Status:_ Accepted. _Context:_ the Tier 2 outputs must be embedded in a versioned contract that prevents silent omissions or non-monotonic percentile bands from leaking into downstream analysis. D-2.4 evaluated the schema migration from the pre-v0 skeleton to a strict v1 bundle contract. _Decision:_ keep the evidence-bundle shape versioned and enforce `schema_version="v1"` semantics for Tier 2, requiring non-null `pd_band`, valid `pd`, and finite financial ratios while keeping the `PDBand` validator strictly monotonic (`p10 <= p50 <= p90`) and immutable (`frozen=True`, `extra="forbid"`). _Consequences:_ the v1 bundle becomes a contract boundary rather than a soft suggestion, ensuring malformed or incomplete Tier 2 outputs are rejected before they can enter any downstream interpretation or reporting stage.

**ADR-033 — Deterministic Financial Ratio Extraction Module (D-2.5)**
_Status:_ Accepted. _Context:_ the Tier 2 module needs a deterministic, audit-friendly way to compute standard SME credit ratios from verified raw features without producing NaN or inf values in edge cases such as zero liabilities or zero interest expense. D-2.5 evaluated ad hoc inline calculations versus a dedicated pure function anchored to the evidence-bundle contract. _Decision:_ implement `compute_financial_ratios(raw_features: dict[str, float | int]) -> dict[str, float]` in `src/tier2_simulation/ratios.py`, mapping canonical raw feature names to the seven standard outputs (`current_ratio`, `quick_ratio`, `debt_to_equity`, `net_profit_margin`, `ebitda_margin`, `interest_coverage`, `asset_turnover`) and applying defensive zero-division guards with finite fallback behavior. Ratios with a zero denominator return a safe finite clamp (e.g. `999.0` for positive numerator cases, `-999.0` for negative numerator cases, `0.0` when both numerator and denominator are zero). _Consequences:_ keeps financial-ratio extraction deterministic and inspectable, guarantees safe handling of edge-case inputs, and provides a clean downstream input for persona reasoning without allowing invalid ratios to contaminate the evidence bundle.

## 7. Open Implementation Notes

Decisions deliberately deferred to implementation time, not yet resolved:

- **Resolved by ADR-027 (formerly open under ADR-017):** XGBoost (unweighted, isotonic calibration) evaluated, promoted, and frozen as the Tier 1 model artifact.
- Exact divergence-score escalation threshold value — pending Phase 5 calibration against the labeled golden set (ADR-004 fixes the _mechanism_, not the _number_).
- Dashboard framework (Streamlit vs. lightweight FastAPI+HTML) — deferred to Phase 6, pending time budget remaining after Phases 4–5.
- Exact HF Inference API model pin (Llama-3.1-8B-Instruct vs. Mistral-7B-Instruct-v0.3, or a current equivalent) — ADR-009 locks the provider and gateway architecture, not the exact model; confirm live availability at Phase 3.
- **Deferred Tier 3 schema fields (fold in as ADR-016 when Phase 4 begins):** `tier3_persona_architecture.md` specifies additional `EvidenceBundle` fields (`tail_loss_estimate`, `covenant_flags`, `revenue_growth_rate`, `pipeline_value_estimate`, `capital_consumption_estimate`, `concentration_flag`) and a `PersonaVerdict.limitations` field that were deliberately excluded from the Phase 0 pre-v0 skeleton. Add these to the typed schema under a new `schema_version` (v2 or per the versioning sequence in ADR-014) and log as ADR-016 at Phase 4 start.
- **Recommendation enum canonical spelling:** `"reject"` is the locked value (not `"decline"`). This is enforced by the `Literal` type in `src/schemas/evidence_bundle.py` `PersonaVerdict.recommendation`. Phase 4 system prompts and rubrics must use `"reject"` exactly.

## 8. Update Protocol

This document is updated **at the close of each roadmap phase**, not continuously during one. At each phase close:

1. Update the §2 status table row for that phase from "Not started" to its actual outcome (including partial/blocked, if honest reporting requires it — this table does not get rounded up).
2. Any decision made during that phase that confirms, refines, or reverses an existing ADR gets a **new** ADR entry that explicitly supersedes the old one; existing ADR entries are never silently edited or deleted, so the decision history stays intact.
3. Any item resolved from §7 Open Implementation Notes is removed from that list and recorded as a new ADR entry.
4. §3 (diagram) and §5 (data flow) are updated to describe the actual code structure once it exists, replacing the planning-stage version rather than annotating it.
5. §9 (below) is reviewed and pruned of anything that shipped during the phase.

## 9. Future Enhancements

Explicitly out of current scope, held here rather than in the PRD's non-goals so they aren't lost:

- Loan-size-scaled divergence thresholds (deferred from MVP per the PRD's resolved decisions).
- Self-consistency majority voting across repeated persona calls (deferred from MVP per the PRD's resolved decisions).
- Long-term drift monitoring on persona "voice" (e.g., detecting a persona growing systematically more conservative across model/prompt updates).
- RAG-based ingestion of unstructured qualitative sources, if a future iteration moves beyond structured input fields.
- Portfolio-level aggregation across multiple reports, as opposed to the current single-file scope.
