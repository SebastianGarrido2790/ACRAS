# ACRAS: Agentic Credit Risk & Analysis System

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Package Manager: uv](https://img.shields.io/badge/uv-fast%20packaging-purple.svg)](https://github.com/astral-sh/uv)
[![Orchestration: LangGraph](https://img.shields.io/badge/orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Contract: Pydantic AI](https://img.shields.io/badge/schema-Pydantic--AI-green.svg)](https://github.com/pydantic/pydantic-ai)
[![Data Governance: DVC + GX](https://img.shields.io/badge/governance-DVC%20%2B%20Great%20Expectations-blueviolet.svg)](https://dvc.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE.txt)

> **ACRAS** assesses Small and Medium-sized Enterprise (SME) credit risk by fusing a calibrated, frozen machine learning model with a parallel multi-agent interpretation layer. It generates an auditable executive risk report—with authentic credit-committee disagreement explicitly surfaced and quantified—in minutes instead of days, supporting Risk Managers and Credit Committees in making defensible decisions.

---

## 📌 Table of Contents

- [Problem Framing & Value Proposition](#-problem-framing--value-proposition)
- [System Architecture (3-Tier Hybrid)](#-system-architecture-3-tier-hybrid)
- [Key Features & Non-Negotiable Invariants](#-key-features--non-negotiable-invariants)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Documentation Index](#-documentation-index)
- [Getting Started](#-getting-started)
- [Development Workflow & Commands](#-development-workflow--commands)
- [License & Authors](#-license--authors)

---

## 🎯 Problem Framing & Value Proposition

Traditional SME credit underwriting suffers from a structural tradeoff between speed and defensibility:
- **Speed Bottleneck:** Manual underwriting takes 5–10 business days as analysts sequentially pull financials, compute ratios, and draft narrative memos.
- **Explainability Gap:** A point-estimate Probability of Default (PD) from an ML model lacks committee-level reasoning and cannot articulate *why* a marginal deal should be approved or declined.
- **Consensus Bias:** Naive LLM summarizers collapse internal tensions, artificially smoothing over the genuine conflict between risk mitigation, commercial growth, and cost of capital.

**ACRAS solves this by:**
1. **Accelerating Underwriting:** Compresses standard evaluation turnaround from 5–10 days to **under 15 minutes**.
2. **Expanding to Risk Distributions:** Replaces point-estimate PDs with vectorized **Monte Carlo simulations (P10/P50/P90 loss and default bands)**.
3. **Simulating a Committee with Genuine Disagreement:** Parallel persona agents (CRO, Growth Director, Capital Allocation Director) evaluate the same typed evidence bundle independently and compute a deterministic **Divergence Score**.
4. **Enforcing Strict Governance & HITL:** Automatically routes high-divergence or low-confidence files to **Human-in-the-Loop (HITL)** review. No loan is ever auto-approved.

---

## 🏛 System Architecture (3-Tier Hybrid)

ACRAS follows the **Deterministic Core / Probabilistic Shell** architectural axiom: calculations are deterministic, immutable, and strictly validated; LLMs are utilized strictly for role-conditioned interpretation.

```
                           ┌─────────────────────────────┐
                           │      Company Profile        │
                           │   (Financials & Metadata)   │
                           └──────────────┬──────────────┘
                                          │
                                          ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │ TIER 1: FROZEN ML CORE (Deterministic)                                 │
     │ - Promoted Model: XGBoost (Unweighted, Isotonic Calibration) [ADR-027] │
     │ - Shared Yeo-Johnson Skew Preprocessing (94 Canonical Features)        │
     │ - Dual Release Gate (INV-3 / FR12): Brier = 0.020766, ROC-AUC = 0.9595 │
     │ - Produces Calibrated PD & Discrete Credit Rating (AAA to CCC/C)       │
     │ - Served via Lean FastAPI Microservice (Zero MLflow Runtime Dep)       │
     └────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │ TIER 2: MONTE CARLO ENGINE (Deterministic)                             │
     │ - Vectorized Simulation (NumPy, N ≥ 10,000 iterations)                 │
     │ - Computes Loss & Default Distributions (P10 / P50 / P90 Bands)        │
     └────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │ STRUCTURED EVIDENCE BUNDLE (Pydantic Contract Schema v1/v2)            │
     │ - PD + Monte Carlo Bands + Rating (AAA–CCC) + Financial Ratios         │
     └────────────────────────────────────┬───────────────────────────────────┘
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   │                                             │
                   ▼                                             ▼
     ┌───────────────────────────┐                 ┌───────────────────────────┐
     │ DATA SCIENTIST AGENT      │                 │ FINANCIAL ANALYST AGENT   │
     │ - Maps PD → Rating        │                 │ - Computes EBITDA, Ratios │
     └─────────────┬─────────────┘                 └─────────────┬─────────────┘
                   │                                             │
                   └──────────────────────┬──────────────────────┘
                                          │
                                          ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │ LLM GATEWAY (Circuit Breaker + Provider Fallback)                      │
     └─────────────┬──────────────────────┬──────────────────────┬────────────┘
                   │                      │                      │
                   ▼                      ▼                      ▼
     ┌────────────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
     │ CRO PERSONA NODE       │ │ GROWTH DIRECTOR   │ │ CFO / CAPITAL DIR.    │
     │ Focus: Downside risk,  │ │ Focus: Revenue,   │ │ Focus: Capital cost,  │
     │ tail loss, covenants   │ │ client lifetime   │ │ hurdle rates, ROE     │
     └─────────────┬──────────┘ └─────────┬─────────┘ └──────────┬────────────┘
                   │                      │                      │
                   └──────────────────────┼──────────────────────┘
                                          │
                                          ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │ CONVERGENCE NODE (Evaluator)                                           │
     │ - Computes Deterministic Divergence Score across Persona Verdicts      │
     │ - Validates schema integrity and evidence grounding                    │
     └────────────────────────────────────┬───────────────────────────────────┘
                                          │
                          ┌───────────────┴───────────────┐
                          │                               │
                [ Divergence < Threshold ]      [ Divergence ≥ Threshold ]
                          │                               │
                          ▼                               ▼
     ┌────────────────────────────┐              ┌────────────────────────────┐
     │ DECISION-READY REPORT      │              │ HUMAN-IN-THE-LOOP (HITL)   │
     │ (Executive Risk Memo)      │              │ ESCALATION FLAG            │
     └────────────────────────────┘              └────────────────────────────┘

---

## 🚦 Roadmap & Implementation Status

| Milestone | Scope & Deliverables | Status | Reference |
| :--- | :--- | :---: | :--- |
| **Phase 0** | **Scaffolding & Data Contracts:** uv environment, Great Expectations suite, DVC remote (6,819 rows × 96 columns pinned), pre-v0 evidence bundle schema, MLflow tracking, CI pipeline with adversarial gate tests. | **Complete** | ADR-010 to ADR-015 |
| **Phase 1** | **Tier 1 ML Core:** 94 canonical feature schema (ADR-024), shared Yeo-Johnson transform (ADR-025), zero outlier deletion (ADR-026), 12-model training benchmark, dual calibration gate (INV-3 / FR12), promoted XGBoost isotonic model (ADR-027), PD-to-rating mapping (ADR-021), lean FastAPI microservice (ADR-022 / ADR-023), hardened container image. | **Complete** | ADR-017 to ADR-027 |
| **Phase 2** | **Tier 2 Monte Carlo Engine:** Vectorized simulation engine generating P10/P50/P90 loss and default bands across 10,000 iterations. | *Up Next* | PRD FR5–FR7 |
| **Phase 3** | **LLM Gateway & Circuit Breaker:** Multi-provider resilience (Gemini primary + open-source secondary), timeout & failover state machine. | *Pending* | ADR-006 / ADR-009 |
| **Phase 4** | **Tier 3 Multi-Agent Personas:** Parallel LangGraph fan-out for CRO, Growth, and Capital personas with deterministic divergence scoring. | *Pending* | ADR-004 / ADR-005 |
| **Phase 5** | **Evaluation Harness & Golden Dataset:** Automated calibration and divergence release gates, LLM-as-judge grounding checks. | *Pending* | PRD FR12–FR13 |
| **Phase 6** | **Dashboard & Trace Logging:** Interactive risk officer UI and structured run persistence. | *Pending* | PRD FR8 |
| **Phase 7** | **Integration & Close-Out:** End-to-end system audits, documentation finalization. | *Pending* | PRD |

```

---

## 🛡 Key Features & Non-Negotiable Invariants

| ID | Invariant & Rule | Architectural Rationale |
| :--- | :--- | :--- |
| **INV-1** | **Deterministic Isolation** | Tiers 1 & 2 never accept LLM-generated text as an input to mathematical calculations. |
| **INV-2** | **Typed Evidence Bundles** | All inter-tier and inter-agent communication flows exclusively through strict Pydantic schemas. |
| **INV-3** | **Dual Model Promotion Gate** | Candidate models must pass **both** discrimination (AUC/KS) and calibration (Brier Score / reliability curve) checks. |
| **INV-4** | **Deterministic Divergence** | Persona disagreement is measured via deterministic mathematical functions over structured verdict fields—never an LLM judge. |
| **INV-5** | **Uniform Low Temperature** | Divergence is engineered through role-specific rubrics and derived metrics, never by increasing LLM temperature. |
| **INV-6** | **Circuit Breaker Gateway** | Every external LLM call routes through an isolated gateway with timeout and automatic secondary-provider failover. |
| **INV-7** | **Data Contract Enforcement** | Great Expectations checks gate the DVC pipeline; schema drift or invalid data halts execution before training. |
| **INV-10** | **Human Authority** | The system produces decision-support recommendations; it never executes automatic credit approvals. |

---

## 💻 Technology Stack

- **Core & Typing:** Python 3.12, Pydantic v2, Pyright / Basedpyright (Strict type coverage)
- **Dependency Management:** [uv](https://github.com/astral-sh/uv)
- **Deterministic Modeling:** scikit-learn, XGBoost, LightGBM, NumPy (Vectorized Monte Carlo)
- **Microservices & API:** FastAPI, Uvicorn
- **Agent Orchestration:** LangGraph (Fan-out/Fan-in Graph), Pydantic AI
- **LLM Gateway & Inference:** Google Gemini API (Primary) + Fallback Provider via custom circuit breaker
- **MLOps & Governance:** DVC (Data Version Control), MLflow (Experiment Tracking & Model Registry), Great Expectations (Data Contracts)
- **Evaluation & Testing:** Pytest, DeepEval (Grounding & Faithfulness)
- **Containerization & CI:** Docker, Docker Compose, GitHub Actions

---

## 📂 Project Structure

```text
ACRAS/
├── src/
│   ├── tier1_ml/              # Lean FastAPI serving microservice (zero MLflow dep, ADR-010/022)
│   │   ├── app.py             # FastAPI application (/health, /predict)
│   │   ├── service.py         # Model loader & inference scoring engine
│   │   ├── schemas.py         # Thin request/response schemas with canonical feature validation (ADR-023)
│   │   └── rating.py          # Calibrated PD to discrete rating bracket mapping (ADR-021)
│   ├── tier2_simulation/      # Vectorized Monte Carlo risk distribution engine (Phase 2)
│   ├── agents/                # Multi-agent persona interpretation layer (Phase 4)
│   │   ├── prompts/           # Role-conditioned persona rubrics & system prompts
│   │   ├── tools/             # Bounded analytical tool endpoints
│   │   └── orchestration/     # LangGraph state graph & convergence evaluator
│   ├── gateway/               # LLM gateway, rate limiter, and circuit breaker (Phase 3)
│   ├── pipelines/             # Deterministic training & feature engineering pipelines
│   │   ├── feature/           # Split & Yeo-Johnson transforms (ADR-024/025/026)
│   │   ├── training/          # 12-config model training, calibration & promotion (ADR-027)
│   │   ├── data_contracts.py  # Great Expectations data contracts (ADR-013)
│   │   ├── validate_gate.py   # DVC validation gate runner (INV-7 / ADR-007)
│   │   └── tracking.py        # MLflow experiment tracking wiring
│   ├── schemas/               # Cross-tier contract schemas (EvidenceBundle, CANONICAL_FEATURES)
│   ├── config/                # Strongly-typed loader for params.yaml
│   └── utils/                 # Logging, exception handling, and custom error types
├── reports/
│   ├── docs/                  # Six Pillars of Groundedness documentation
│   │   ├── architecture/      # system_design.md (Living ADR ledger: ADR-001 through ADR-027)
│   │   ├── groundedness/      # canvas.md, project_charter.md, prd.md, user_story.md, roadmap.md
│   │   ├── evaluations/       # model_leaderboard.md, capability_profile_gates.md
│   │   ├── decisions/         # Phase implementation plans & Post-Implementation Reviews (PIRs)
│   │   ├── workflows/         # Phase execution plans & falsification matrices
│   │   └── runbooks/          # challenges_and_solutions_guide.md
│   └── model_leaderboard.csv  # Machine-readable 12-configuration benchmark metrics
├── tests/
│   ├── unit/                  # Unit tests (config, features, transforms, pipeline, gates, serving)
│   └── integration/           # Integration tests (adversarial gate, container live scoring)
├── artifacts/                 # Promoted frozen model bundle & feature transformer (gitignored)
├── params.yaml                # Global parameters, split ratios, seeds, thresholds & rating table
├── pyproject.toml             # uv package management, tool configs, dependency groups
├── Dockerfile                 # Hardened multi-stage serving image (non-root, zero MLflow runtime)
├── docker-compose.yaml        # Local full-stack orchestration
└── dvc.yaml                   # DVC pipeline definitions
```

---

## 📚 Documentation Index

The complete architectural, product, and governance documentation set is organized into the **Six Pillars of Groundedness** under `reports/docs/`:

| Document | Purpose & Description |
| :--- | :--- |
| **[Machine Learning Canvas](reports/docs/groundedness/canvas.md)** | Strategic one-page overview of business value, ML objectives, simulation tiers, and evaluation metrics. |
| **[Project Charter](reports/docs/groundedness/project_charter.md)** | Project scope, target personas, ROI appraisal, Definition of Done, and cost models. |
| **[User Stories & Problem Framing](reports/docs/groundedness/user_story.md)** | Stakeholder personas, 5 Whys root cause analysis, Jobs-to-be-Done, and user journeys. |
| **[Product Requirements Document (PRD)](reports/docs/groundedness/prd.md)** | Functional requirements (FR1–FR13), non-functional requirements, release gates, and governance rules. |
| **[Technical Roadmap](reports/docs/groundedness/technical_roadmap.md)** | Phased engineering execution plan (Phase 0 through Phase 7) with explicit exit criteria. |
| **[System Design & ADRs](reports/docs/architecture/system_design.md)** | Living system architecture specification and formal decision ledger (**ADR-001 through ADR-027**). |
| **[Model Evaluation Leaderboard](reports/docs/evaluations/model_leaderboard.md)** | Auditable benchmark report of all 12 trained/calibrated model configurations with sample density caveats. |
| **[Challenges & Solutions Guide](reports/docs/runbooks/challenges_and_solutions_guide.md)** | Operational runbook mapping anticipated/encountered failure modes to validated solutions. |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) installed
- Git & Docker (optional, for containerized execution)

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/SebastianGarrido2790/ACRAS.git
cd ACRAS

# Create virtual environment and install locked dependencies
uv sync
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and set your API keys:
```bash
cp .env.example .env
# Edit .env with your GEMINI_API_KEY and fallback provider credentials
```

### 3. Run the Service Locally
```bash
# Launch FastAPI / Agent service
uv run python main.py
```

---

## 🛠 Development Workflow & Commands

| Task | Command | Description |
| :--- | :--- | :--- |
| **Run Full Test Suite** | `uv run pytest` | Executes unit, integration, and eval test suites. |
| **Lint & Format Check** | `uv run ruff check .` | Enforces linting, import sorting, and formatting rules. |
| **Type Checking** | `uv run pyright` | Validates strict static typing across `src/` and `tests/`. |
| **Reproduce Data Pipeline** | `uv run dvc repro` | Executes DVC pipeline gated by Great Expectations checks. |
| **Train & Benchmark Models** | `uv run python -m src.pipelines.training.train --output-csv reports/model_leaderboard.csv` | Trains 12 configurations, computes calibration metrics, logs to MLflow. |
| **Promote & Export Winner** | `uv run python -m src.pipelines.training.promote` | Gated model promotion (INV-3) & lean bundle serialization. |
| **Launch Tier 1 API** | `uv run python -m uvicorn src.tier1_ml.app:app --host 0.0.0.0 --port 8000` | Starts the lean Tier 1 FastAPI microservice. |
| **Build Tier 1 Serving Image** | `docker build -t acras-tier1:latest .` | Builds lean, hardened serving container without training dependencies. |

| **Experiment Tracking** | `uv run mlflow ui` | Launches local MLflow dashboard for model tracking. |
| **Docker Build & Run** | `docker compose up --build` | Builds and launches all services via Docker Compose. |

---

## 📄 License & Authors

- **Author:** Sebastián Garrido Arévalo
- **License:** [MIT License](LICENSE.txt)
