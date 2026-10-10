# Implementation Roadmap — ACRAS (Agentic Credit Risk & Analysis System)

**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-28 (rechartered 2026-10-09) · **Status:** Phases 0–2 complete; Phases 3–7 sequenced

---

## Document Overview

- **What it is:** A non-authoritative, high-level sequencing file: major capabilities, dependency order, and evidence-based phase exit criteria from Phase 0 through Phase 7.
- **Why it exists:** Expresses what gets built, in what dependency order, and what evidence unlocks the next stage — nothing more.
- **How to use it:** Read for sequencing and exit gates only. For decisions, see phase implementation plans (`reports/docs/decisions/`, `reports/docs/phases/`); for architecture, see `reports/docs/architecture/system_design.md`; for feature behavior, see specifications; for procedure, see skills and workflows.

> This file is deliberately non-authoritative. It MUST NOT contain detailed technical specifications, file-by-file instructions, algorithms, individual requirements, task lists, technical decisions, agent prompts, or detailed architecture. Those belong in phase plans, ADRs, specifications, and code. If this file and an authoritative artifact disagree, the authoritative artifact wins — surface the conflict rather than editing this file to overrule it.

It answers: *what major capabilities do we expect to build, in what dependency order, and what evidence unlocks the next stage?*

---

## Phase 0 — Scaffolding & Data Contracts ✅ **Complete** (closed 2026-09-21)

**Goal:** Stand up the repo, tracking infrastructure, and the data-contract gate before any modeling begins.

**Capabilities:**
- repository structure and CI baseline
- DVC-tracked dataset with isolated remote
- Great Expectations data-contract gate
- pre-v0 evidence-bundle contract

**Exit criteria:**
- deliberately corrupted data sample demonstrably halted by the GX gate before training.

**Dependencies:** none.

---

## Phase 1 — Tier 1 Frozen ML Core ✅ **Complete** (closed 2026-10-02)

**Goal:** Train, validate, and serve a calibrated PD model — the deterministic foundation every other tier depends on.

**Capabilities:**
- calibrated PD model (discrimination + calibration gates)
- frozen, versioned model artifact
- FastAPI serving layer aligned to the evidence-bundle contract

**Exit criteria:**
- deliberately miscalibrated candidate demonstrably blocked at promotion despite strong AUC;
- live endpoint returns a PD for a sample request.

**Dependencies:** Phase 0.

---

## Phase 2 — Tier 2 Monte Carlo Risk Distribution ✅ **Complete** (closed 2026-10-08)

**Goal:** Replace the point PD with a defensible risk distribution.

**Capabilities:**
- vectorized Monte Carlo engine (N ≥ 10,000)
- closed-form analytical benchmark and tolerance gate
- evidence-bundle schema v1 (P10/P50/P90)
- sub-5ms latency benchmark

**Exit criteria:**
- simulation output matches the analytical benchmark within defined tolerance;
- runtime stays in the sub-5ms budget at N=10,000.

**Dependencies:** Phase 1.

---

## Phase 3 — LLM Gateway & Provider Resilience

**Goal:** Build the resilience infrastructure Tier 3 will depend on *before* Tier 3 exists.

**Capabilities:**
- provider-abstracted LLM gateway
- circuit breaker with defined failure thresholds
- fallback observability and cost logging

**Exit criteria:**
- forced primary-provider failure results in automatic fallback with no unhandled exception, logged and observable.

**Dependencies:** none technically; sequenced here because Phase 4 needs it in place.

---

## Phase 4 — Tier 3 Multi-Agent Persona Layer

**Goal:** Build the persona nodes and the deterministic convergence node — the structural heart of the system.

**Possible capabilities:**
- persona agents with rubric-conditioned interpretation
- structured verdict contract
- deterministic divergence scoring and HITL escalation
- orchestrator assembling the executive report

**Exit criteria:**
- happy-path case produces a coherent end-to-end report;
- engineered-divergence case produces genuinely different verdicts across personas.

**Dependencies:** Phase 1 (evidence data), Phase 2 (P10/P50/P90 fields), Phase 3 (gateway).

---

## Phase 5 — Evaluation Harness & Governance Gates

**Goal:** Turn designed calibration and divergence rules into automated, enforced checks.

**Possible capabilities:**
- versioned golden dataset
- automated calibration gate
- automated divergence gate
- grounding and regression checks wired into CI

**Exit criteria:**
- deliberately miscalibrated model *and* deliberately non-divergent Tier 3 configuration both demonstrably blocked by CI.

**Dependencies:** Phase 1 (model to gate), Phase 4 (Tier 3 to gate).

---

## Phase 6 — Dashboard & Audit Layer

**Goal:** Usable Risk Manager interface with every report fully auditable after the fact.

**Possible capabilities:**
- report input/view interface
- machine-readable trace persistence
- escalation-state surfacing

**Exit criteria:**
- completed report fully reconstructible from stored trace logs alone, without re-running the pipeline.

**Dependencies:** Phase 4, Phase 5.

---

## Phase 7 — Integration & Documentation Close-Out

**Goal:** Consolidate all tiers against acceptance scenarios and close out the documentation set.

**Possible capabilities:**
- end-to-end acceptance validation
- as-built architecture record
- finalized runbook and published repo

**Exit criteria:**
- every item in the Charter's Definition of Done satisfied.

**Dependencies:** all prior phases.

---

## Dependency Order & De-Scope Lever

Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 is a strictly linear dependency chain: each tier consumes the previous tier's real output rather than a mock, so no phase runs meaningfully in parallel with another.

Explicit de-scope lever, decided now rather than under deadline pressure: if the schedule runs long, cut **Phase 6 interface polish first** (degradable to a CLI or notebook-driven path) — never eval rigor (Phase 5) or acceptance criteria (Phase 7).
