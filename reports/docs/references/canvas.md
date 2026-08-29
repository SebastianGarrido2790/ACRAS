# Machine Learning Canvas - ACRAS (Agentic Credit Risk & Analysis System)

| Product                                             | Authors                   | Date       | Version                   |
| --------------------------------------------------- | ------------------------- | ---------- | ------------------------- |
| ACRAS — Hybrid Agentic MLOps System for Credit Risk | Sebastián Garrido Arévalo | 2026-08-28 | 2.0 (three-tier redesign) |

---

## Document Overview

- **What it is:** A structured Machine Learning & System Canvas capturing the business value, ML objectives, probabilistic risk simulation, multi-agent architecture, data governance, and evaluation strategy for ACRAS.
- **Why it exists:** Provides a single-pane-of-glass architectural and strategic overview, defining technical boundaries, risk tiers, and success criteria prior to implementation.
- **How to use it:** Use this document for high-level project orientation, understanding tier separations (frozen ML core vs. Monte Carlo engine vs. multi-agent interpretation), and aligning development with system goals and constraints.

---

## 1. Background

SME (Small and Medium-sized Enterprise) lenders scale loan volume by adding analyst headcount, not by making underwriting faster per file. A human credit analyst typically needs 5–10 days to pull financial statements, bureau history, and qualitative signals (sector, management tenure, covenant history) into a single lending recommendation. Two structural problems sit underneath that delay:

- **Throughput is headcount-bound.** Volume growth requires proportional hiring, not process improvement.
- **A point score is not a decision.** Regulatory and audit requirements mean a lending decision must be explainable and contestable, not just accurate. A raw PD (probability of default) number from a model has no committee-level reasoning behind it, it doesn't say _why_ a marginal file should or shouldn't be approved, and it doesn't capture the tension a real credit committee holds between risk exposure, growth appetite, and cost of capital.

## 2. Value Proposition

ACRAS replaces a single point PD estimate with a full decision-support artifact: a calibrated risk _distribution_ (not one number), interpreted independently by three specialist perspectives that mirror the built-in tension of a real credit committee: risk, growth, and capital cost, synthesized into one auditable executive report in minutes rather than days. Every number in the report is a traceable, deterministic calculation; only the _interpretation_ around those numbers is delegated to LLM reasoning, and where the three perspectives genuinely disagree, the report says so instead of averaging the disagreement away.

## 3. Objectives

1. Cut turnaround for a standard SME file from 5–10 days to under 15 minutes.
2. Replace point-estimate PD with a full risk-distribution view (P10 / P50 / P90 loss and default bands).
3. Produce a report that can surface real disagreement between risk / growth / capital perspectives, not a single blended recommendation.
4. Keep every quantitative claim traceable to a deterministic calculation — never an LLM-generated number.
5. Route any file where the agents disagree beyond a defined threshold, or where model confidence is low, to human sign-off rather than auto-resolving it.

## 4. Solution

**Features / architecture:**

- **Tier 1 (frozen ML core):** a gradient-boosted PD model (XGBoost/LightGBM) trained on structured financial/repayment data, served behind a FastAPI microservice.
- **Tier 2 (risk distribution):** a vectorized Monte Carlo engine (N ≈ 10,000 draws) that turns the Tier 1 model's output into P10/P50/P90 loss and default bands instead of one number.
- **Tier 3 (parallel interpretation):** a LangGraph fan-out/fan-in graph — CRO (Chief Risk Officer), Portfolio Growth Director, and CFO/Capital Allocation Director nodes read one shared, typed evidence bundle in parallel; a convergence node reconciles their positions or escalates on material disagreement.
- **Supporting agents:** a Data Scientist Agent that calls the FastAPI endpoint and converts probability into a credit rating (e.g., AAA–CCC); a Financial/Domain Analyst Agent that computes financial ratios (EBITDA, margins) and interprets qualitative fields; an Orchestrator that aggregates everything into the final report.
- **Interface:** a lightweight dashboard for a Risk Manager to enter a company profile and view the generated report.
- **Resilience layer:** an LLM gateway with a circuit breaker and a secondary-provider fallback (primary + backup LLM provider), so a single provider outage doesn't take the system down.
- **Data governance:** a Great Expectations data-contract gate in front of the DVC training pipeline — a failed expectation halts training before a bad model can be produced.

**Integration:** self-contained demo stack (FastAPI + LangGraph service + dashboard); no live core-banking integration.

**Constraints:** synthetic/public data only, no PII; no auto-approval — the system produces a recommendation, not a binding decision; single-session execution (no persistent cross-application memory); a hard per-report LLM cost ceiling.

**Out of scope (this iteration):** fraud detection, real-time transaction monitoring, portfolio-level stress testing, retail (non-SME) credit, and generation of actual regulatory adverse-action filings.

## 5. Feasibility

Solo build. An earlier single-tier version of ACRAS already proved the core pattern — FastAPI-served model wrapped as an agent tool, DVC/MLflow-tracked training — so Tier 1 is de-risked. The open technical risk is Tier 3: whether three LLM personas reading identical evidence produce _genuinely_ different reasoning or just three stylistic rewordings of the same conclusion. That's a prompt-design and evaluation problem, not an architecture problem, and it's treated as a first-class risk below rather than assumed away. Free-tier LLM usage (Gemini + a secondary provider) is sufficient at portfolio scale. Public SME/credit datasets (e.g., corporate bankruptcy or SME loan-default sets on Kaggle/UCI) remove any need for proprietary data access.

## 6. Data

- **Training data:** a public structured credit-risk dataset (financial ratios + historical default/no-default label), schema-validated by Great Expectations before DVC tracks a new version.
- **Production/demo input:** synthetic company profiles (financial statement fields, requested loan amount/term, structured qualitative fields such as sector and covenant history) entered through the dashboard — deliberately structured rather than free-text/scraped, to avoid a training/production mismatch and an unnecessary live-internet dependency in a demo system.
- **Labeling:** inherited default/no-default label from the source dataset; no manual labeling required for Tier 1.
- **Evaluation set:** a hand-authored golden set (~20–40 cases), purpose-built to exercise specific failure modes (marginal PD, strong-growth-thin-capital divergence case, tool failure, missing fields) rather than randomly sampled, since there is no live production traffic to sample from yet.

## 7. Metrics

- **Model quality:** AUC-ROC / KS-statistic for separation, **calibration (Brier score / reliability curve)** as a first-class gate — the Monte Carlo bands and every downstream rating are only meaningful if the probabilities are calibrated, not just well-ranked.
- **System:** turnaround time per file (target < 15 min); cost per report (target < $0.15); % of runs completing without fallback/circuit-breaker triggering.
- **Decision quality (the metric that validates Tier 3 isn't theater):** % of divergence-engineered golden-set cases where the three personas actually register materially different positions.
- **Evaluation harness:** LLM-as-judge pass rate on grounding/no-hallucinated-figures criteria across the golden set.

## 8. Evaluation

**Offline:** the full pipeline runs against the golden set before any deployment; an LLM-as-judge checks grounding and flags any invented figure; a fixed subset of cases is checked specifically for genuine cross-persona divergence. Regression tests re-run on every prompt or model change.

**Online (demo-scale):** every report carries a machine-readable trace — tool calls made, fallback triggered (if any), PD/Monte Carlo bands, and each persona's verdict — so a report can be audited after the fact even without a live end-user feedback loop.

## 9. Modeling

Ship Tier 1 first and freeze it once validated on held-out data; wrap it behind FastAPI unchanged. Build Tier 2 purely as a downstream consumer of Tier 1's output distribution — no retraining required to add it. Build Tier 3 against a frozen, versioned evidence-bundle schema so that agent/prompt iteration never touches the model or the simulation engine. The model itself is retrained only on a fixed cadence or on data-contract drift, never reactively mid-iteration on the agent layer.

## 10. Inference

Synchronous, per-request inference — one company record in, one full multi-tier report out. No batch requirement. Wall-clock time is dominated by LLM round-trips (Tier 3), not by the ML or Monte Carlo layers, which run in milliseconds.

## 11. Feedback

Primary loop (no live loan book to draw from): the golden/adversarial evaluation set itself, expanded every time a new failure mode is discovered during build or demo use. If ever connected to a real credit committee, the highest-signal feedback would be analyst overrides of the Orchestrator's final recommendation — that signal is what would recalibrate the convergence node's disagreement threshold over time.

## 12. Project

- **Team:** solo (Sebastián Garrido Arévalo).
- **Deliverables:** Tier 1 FastAPI microservice, Tier 2 Monte Carlo module, Tier 3 LangGraph multi-agent system, dashboard, evaluation harness, GX/DVC data-contract pipeline, and the full planning/documentation set (this canvas, the project charter, PRD, technical roadmap, system design ADR, and challenges/solutions runbook).
- **Timeline:** phased delivery mapped to the remaining sessions of the Professional Certificate in Agentic AI (through late September 2026), so each certificate lab is a strict subset of what's already shipped in ACRAS.
