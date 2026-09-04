# System Design — Architectural Decision Record

**Project:** ACRAS (Agentic Credit Risk & Analysis System)
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-28 · **Status:** Phase 0 stub — pre-implementation

> This document reflects the **actual implemented state** of the system. At Phase 0, that state is "not yet built" — every component and diagram below is a planning-stage placeholder, explicitly marked as such, not a description of working code. It is updated at the close of each roadmap phase per the Update Protocol in §8; nothing here should be read as "done" until a phase's exit criteria have actually been demonstrated.

---

## Document Overview

- **What it is:** The primary System Design specification and Architectural Decision Record (ADR) detailing system topology, data flow, component interfaces, evidence-bundle contracts, and formal architectural decisions (ADR-001 through ADR-008).
- **Why it exists:** Codifies the immutable architectural boundaries (deterministic ML/simulation core vs. non-deterministic LLM reasoning layer), maintains a living record of implementation progress, and preserves technical decision rationale.
- **How to use it:** Refer to this document during component design and integration to adhere to architectural boundaries and interface schemas; update the status table and architecture specifications at the close of each development phase per the Update Protocol (§8).

---

## 1. Architecture Overview

ACRAS is a three-tier decision-support system built on one non-negotiable boundary: **Tiers 1 and 2 are deterministic and versioned; Tier 3 is the only layer where non-deterministic (LLM) reasoning is permitted.** A single typed evidence-bundle contract is the sole channel through which information crosses tier boundaries — no tier reads another tier's internal state directly, and no LLM output is allowed to become an input to a deterministic calculation. Tier 1 produces a calibrated probability of default; Tier 2 expands that into a risk distribution; Tier 3 fans out to three independently-mandated persona agents that interpret the same evidence in parallel and converge (or explicitly diverge) into one executive report.

## 2. Current Implementation Status

| Component                                                 | Status       | Notes                                           |
| --------------------------------------------------------- | ------------ | ----------------------------------------------- |
| Planning docs (Canvas, Charter, PRD, User Story, Roadmap) | **Complete** | This ADR is the next artifact in that sequence. |
| Phase 0 — Scaffolding & data contracts                    | Not started  | —                                               |
| Phase 1 — Tier 1 ML core                                  | Not started  | —                                               |
| Phase 2 — Tier 2 Monte Carlo                              | Not started  | —                                               |
| Phase 3 — LLM gateway & circuit breaker                   | Not started  | —                                               |
| Phase 4 — Tier 3 multi-agent core                         | Not started  | —                                               |
| Phase 5 — Evaluation harness & governance gates           | Not started  | —                                               |
| Phase 6 — Dashboard & trace logging                       | Not started  | —                                               |
| Phase 7 — Integration & doc close-out                     | Not started  | —                                               |

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

| Component                            | Planned Responsibility                                                                               | Status  |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------- | ------- |
| Tier 1 FastAPI service               | Serve the frozen, calibrated PD model                                                                | Planned |
| Tier 2 Monte Carlo module            | Convert Tier 1 output into P10/P50/P90 bands                                                         | Planned |
| Evidence-bundle schema               | Single typed contract shared by all tiers                                                            | Planned |
| LLM Gateway                          | Custom, `pybreaker`-backed interface over Gemini (primary) and HF Inference API (fallback) — ADR-009 | Planned |
| Circuit breaker                      | Halts calls to a failing provider, triggers fallback                                                 | Planned |
| Data Scientist Agent                 | Calls Tier 1 endpoint, maps PD → credit rating                                                       | Planned |
| Financial/Domain Analyst Agent       | Computes financial ratios from evidence bundle                                                       | Planned |
| CRO / Growth / Capital persona nodes | Independent, rubric-conditioned interpretation, emit `PersonaVerdict`                                | Planned |
| Convergence node                     | Deterministic divergence scoring + HITL escalation branch                                            | Planned |
| Orchestrator                         | Aggregates all agent output into the executive report                                                | Planned |
| Dashboard                            | Risk Manager–facing input/output interface                                                           | Planned |
| GX/DVC pipeline                      | Data-contract gate in front of model training                                                        | Planned |
| Evaluation harness                   | Golden dataset, calibration gate, divergence gate, regression tests                                  | Planned |

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


## 7. Open Implementation Notes

Decisions deliberately deferred to implementation time, not yet resolved:

- Exact model algorithm (XGBoost vs. LightGBM) — pending Phase 1 EDA results.
- Exact divergence-score escalation threshold value — pending Phase 5 calibration against the labeled golden set (ADR-004 fixes the _mechanism_, not the _number_).
- Dashboard framework (Streamlit vs. lightweight FastAPI+HTML) — deferred to Phase 6, pending time budget remaining after Phases 4–5.
- Exact HF Inference API model pin (Llama-3.1-8B-Instruct vs. Mistral-7B-Instruct-v0.3, or a current equivalent) — ADR-009 locks the provider and gateway architecture, not the exact model; confirm live availability at Phase 3.

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
