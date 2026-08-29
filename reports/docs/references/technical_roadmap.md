# Technical Roadmap — ACRAS (Agentic Credit Risk & Analysis System)

**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-28 · **Version:** 2.0

---

## Document Overview

- **What it is:** A phased, dependency-ordered technical roadmap detailing milestones from Phase 0 (Scaffolding & Data Contracts) through Phase 7 (Documentation Close-out & Final Polish).
- **Why it exists:** Provides an actionable, step-by-step implementation plan with strict deliverables, dependency constraints, and objective exit criteria for each phase.
- **How to use it:** Use this document to plan and track implementation tasks, verify prerequisites before advancing to subsequent phases, and ensure all exit criteria are demonstrably validated.

---

## Assumptions

- Duration estimates are given as low–high ranges to reflect that honestly, per the Charter's own standard — not single-point estimates presented as certain.
- Each phase's exit criteria must be demonstrated, not merely coded — "it runs once on my machine" does not satisfy a phase.
- Phases are ordered by dependency, not by calendar convenience.

## Phase-by-Phase Plan

### Phase 0 — Project Scaffolding & Data Contracts

**Goal:** Stand up the repo, tracking infrastructure, and the data-contract gate before any modeling begins, so nothing downstream is ever built on ungoverned data.

**Key tasks:** initialize repo structure; set up DVC + MLflow tracking; acquire and DVC-version the public SME/credit-risk dataset; define the Great Expectations expectation suite (schema, ranges, null-handling) for the raw data; wire the GX check as a hard gate in front of the DVC training stage; stand up the Docker base image and a GitHub Actions CI skeleton; draft the shared Pydantic evidence-bundle schema (v0) so Tiers 1–3 all target one contract from day one, even before Tier 3 exists.

**Deliverables:** repo scaffold; DVC-tracked dataset; GX expectation suite; CI skeleton; evidence-bundle schema v0.

**Exit criteria:** a deliberately corrupted/invalid data sample is fed to the pipeline and the GX gate demonstrably halts it before training reaches the model.

**Dependencies:** none.

**Estimated duration:** 3–4 days.

---

### Phase 1 — Tier 1: Frozen ML Core

**Goal:** Train, validate, and serve a calibrated PD model — the deterministic foundation every other tier depends on.

**Key tasks:** EDA and feature engineering on the GX-validated dataset; train baseline candidates (XGBoost/LightGBM), tracked in MLflow; compute discrimination (AUC/KS) **and** calibration (Brier score / reliability curve) — this is where FR12 is implemented, not just documented; freeze and register the promoted model version; build the FastAPI endpoint wrapping it, with request/response schema aligned to the evidence-bundle contract; containerize; write endpoint tests.

**Deliverables:** trained, calibrated, versioned model artifact; FastAPI microservice; calibration report.

**Exit criteria:** a deliberately miscalibrated candidate model is run through the promotion check and demonstrably blocked, even with strong AUC; the live endpoint returns a PD for a sample request.

**Dependencies:** Phase 0.

**Estimated duration:** 5–7 days.

---

### Phase 2 — Tier 2: Monte Carlo Risk Distribution Engine

**Goal:** Replace the point PD with a defensible risk distribution.

**Key tasks:** design the vectorized Monte Carlo simulation (NumPy, N ≥ 10,000) consuming Tier 1's output distribution parameters; validate simulation output against a known closed-form benchmark before trusting it downstream; wire it as a pure read-only consumer of Tier 1 (no retraining coupling); extend the evidence-bundle schema to v1 with P10/P50/P90 fields; benchmark runtime.

**Deliverables:** Monte Carlo module; evidence-bundle schema v1; performance benchmark.

**Exit criteria:** simulation output matches the analytical benchmark within a defined tolerance; runtime stays in the sub-5ms budget at N=10,000.

**Dependencies:** Phase 1.

**Estimated duration:** 2–3 days.

---

### Phase 3 — LLM Gateway, Circuit Breaker & Provider Resilience

**Goal:** Build the resilience infrastructure Tier 3 will depend on _before_ Tier 3 exists, so agent development never has to work around an unstable LLM layer.

**Key tasks:** implement an LLM gateway abstraction over a primary provider (Gemini) and a secondary fallback provider; implement a circuit breaker with defined failure thresholds (timeout, consecutive-error count); simulate a primary-provider outage and confirm automatic failover; add token/cost logging at the gateway layer, feeding the per-report cost metric.

**Deliverables:** LLM gateway module; tested circuit breaker; cost-logging hooks.

**Exit criteria:** a forced primary-provider failure results in automatic fallback with no unhandled exception, and the event is logged and observable.

**Dependencies:** none technically; sequenced here because Phase 4 needs it in place.

**Estimated duration:** 2–3 days. _(Thematically overlaps Session 3 — routing, fallback policies, token economics — a bonus, not a deadline.)_

---

### Phase 4 — Tier 3: Multi-Agent Persona Layer (Core)

**Goal:** Build the three persona nodes and the deterministic divergence-scoring convergence node — the structural heart of the redesign.

**Key tasks:** implement the Data Scientist Agent (FastAPI tool call, versioned probability→rating mapping); implement the Financial/Domain Analyst Agent (ratio computation from evidence-bundle fields); implement the CRO / Growth / Capital persona nodes as a LangGraph fan-out, each with its distinct rubric-conditioned prompt and role-specific derived-field emphasis, each emitting the structured `PersonaVerdict`; implement the convergence node's deterministic divergence-score function and HITL escalation branch; implement the Orchestrator that aggregates everything into the executive report; route all LLM calls through the Phase 3 gateway.

**Deliverables:** full Tier 3 LangGraph graph; `PersonaVerdict` schema; divergence-scoring function; Orchestrator; first end-to-end draft report.

**Exit criteria:** a hand-run happy-path case produces a coherent report end-to-end; a hand-run engineered-divergence case produces genuinely different `recommendation`/`lean` values across the three personas — before any formal golden-set evaluation exists.

**Dependencies:** Phase 1 (real evidence data), Phase 2 (P10/P50/P90 fields), Phase 3 (gateway).

**Estimated duration:** 7–10 days — the largest single phase; this is the structurally hardest part of the system, and the estimate reflects that rather than being smoothed to match the calendar. _(The Data Scientist Agent's FastAPI tool contract — idempotency, audit trail — should be built to double as Session 5's Lab 1 deliverable.)_

---

### Phase 5 — Evaluation Harness, Golden Dataset & Governance Gates

**Goal:** Turn the calibration gate (FR12) and divergence gate (FR13) from designed rules into automated, enforced checks.

**Key tasks:** author the ~20–40 golden-set cases (calibration edge cases plus labeled engineered-agree and engineered-diverge scenarios); implement the automated calibration promotion check for Tier 1; calibrate the divergence-score escalation threshold against the labeled golden set (ROC-style operating point, per the resolved PRD decision); implement the automated divergence promotion check for Tier 3; implement an LLM-as-judge grounding check (no invented figures); implement the fixed-settings regression test (same case run twice → same recommendation category); wire all of the above into CI as merge-blocking checks.

**Deliverables:** versioned golden dataset; automated calibration gate; automated divergence gate; grounding check; regression suite; CI wiring.

**Exit criteria:** a deliberately miscalibrated model _and_ a deliberately non-divergent Tier 3 configuration are both demonstrably blocked by CI in a test run — not just theoretically blockable.

**Dependencies:** Phase 1 (model to gate), Phase 4 (Tier 3 to gate).

**Estimated duration:** 5–7 days. _(Directly overlaps Session 6's content — guardrails, LLM-as-judge, golden/adversarial sets, Lab 4 — the closest thematic match in the whole roadmap.)_

---

### Phase 6 — Dashboard, Full Trace Logging & Audit Layer

**Goal:** Give the Risk Manager persona a usable interface and make every report fully auditable after the fact.

**Key tasks:** build a lightweight dashboard (Streamlit or FastAPI+HTML) for company-profile input and report viewing; implement full machine-readable trace logging per report (tool calls, fallback events, PD/MC bands, persona verdicts, divergence score — FR9); persist trace logs; surface HITL escalation state clearly in the UI.

**Deliverables:** working dashboard; trace-log persistence; escalation UI.

**Exit criteria:** a completed report can be fully reconstructed and audited from stored trace logs alone, without re-running the pipeline.

**Dependencies:** Phase 4, Phase 5.

**Estimated duration:** 3–4 days.

---

### Phase 7 — Integration, MAS Consolidation & Documentation Close-Out

**Goal:** Consolidate all tiers, validate against the PRD's three acceptance scenarios, and close out the documentation set.

**Key tasks:** run and pass all three PRD acceptance scenarios end-to-end; update `system_design.md` to reflect the actual-as-built state, superseding the planning-stage description; write `challenges_and_solutions_guide.md` entries for issues actually encountered in Phases 0–6; write the final README and demo walkthrough for the published repo; check the build against the Charter's Definition of Done.

**Deliverables:** fully integrated system passing all three acceptance scenarios; finalized ADR; finalized runbook; published repo.

**Exit criteria:** every item in the Charter's §5 Definition of Done is satisfied.

**Dependencies:** all prior phases.

**Estimated duration:** 4–5 days. _(Thematically overlaps Session 7 — MAS integration, Lab 3, panel advisory.)_

---

## Critical Path

Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 is a strictly linear dependency chain — there is no phase here that can run meaningfully in parallel with another, since each tier is built to consume the previous one's real output rather than a mock. That has a direct consequence for schedule risk, addressed below rather than smoothed over.

## Schedule Risk (Stated Plainly)

Summing the estimates: **31 days at the low end, 43 days at the high end**, starting today (Aug 28, 2026). That means:

- The **low-end estimate lands almost exactly on Session 7**, which is the aggressive case and assumes no rework, and no surprises in Phase 4 (the largest and riskiest phase).
- The **high-end estimate overshoots Session 7 by roughly 11 days**, which is the realistic case for a solo builder.

This roadmap does not paper over that gap with optimistic rounding. If Phase 4 runs long, the most likely place for it given it's the structurally hardest phase, the first thing to cut is **not** eval rigor (Phase 5) or the acceptance criteria (Phase 7); it's **Phase 6's dashboard polish**, which can degrade to a CLI or notebook-driven input/output path without weakening any PRD requirement, acceptance scenario, or governance gate. That's the explicit de-scope lever, decided now rather than under deadline pressure later.

## Dependencies Summary

Public dataset availability and quality (Phase 0); LLM provider API access/quotas for both primary and fallback providers (Phase 3); DVC/MLflow/Great Expectations tooling (Phase 0); solo-builder time running in parallel with certificate Sessions 3–7 (all phases).
