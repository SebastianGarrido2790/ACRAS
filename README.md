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
     │ - Gradient Boosted Model (XGBoost / LightGBM) served via FastAPI       │
     │ - Produces Calibrated Probability of Default (PD) [Brier Score Gated]  │
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
│   ├── tier1_ml/              # Calibrated PD model training & FastAPI serving
│   ├── tier2_simulation/       # Vectorized Monte Carlo risk distribution engine
│   ├── agents/
│   │   ├── prompts/           # Role-conditioned persona rubrics & system prompts
│   │   ├── tools/             # Data Scientist & Financial Analyst tool endpoints
│   │   └── orchestration/      # LangGraph state graph & convergence evaluator
│   ├── gateway/               # LLM gateway, rate limiter, and circuit breaker
│   ├── schemas/               # Evidence bundle & PersonaVerdict Pydantic contracts
│   ├── pipeline/              # Feature extraction, training, and inference pipelines
│   └── utils/                 # Structured logging, metrics, and error handling
├── reports/docs/
│   ├── references/            # Canvas, Project Charter, PRD, User Stories, Roadmap
│   ├── architecture/          # System Design & Architectural Decision Records (ADRs)
│   └── runbooks/              # Challenges & Solutions guide (Runbook)
├── tests/
│   ├── unit/                  # Fast deterministic unit tests (Tiers 1 & 2)
│   ├── integration/           # API and service integration tests
│   └── evals/                 # Golden set evaluation, calibration & divergence gates
├── params.yaml                # Global hyperparameters, simulation counts & thresholds
├── pyproject.toml             # Project dependencies & tool configurations
├── docker-compose.yaml        # Local full-stack orchestration
└── dvc.yaml                   # DVC data pipeline definitions
```

---

## 📚 Documentation Index

The complete architectural, product, and governance documentation set is located in `reports/docs/`:

| Document | Purpose & Description |
| :--- | :--- |
| **[Machine Learning Canvas](reports/docs/references/canvas.md)** | Strategic one-page overview of business value, ML objectives, simulation tiers, and evaluation metrics. |
| **[Project Charter](reports/docs/references/project_charter.md)** | Project scope, target personas, ROI appraisal, Definition of Done, and cost models. |
| **[User Stories & Problem Framing](reports/docs/references/user_story.md)** | Stakeholder personas, 5 Whys root cause analysis, Jobs-to-be-Done, and user journeys. |
| **[Product Requirements Document (PRD)](reports/docs/references/prd.md)** | Functional requirements (FR1–FR13), non-functional requirements, release gates, and governance rules. |
| **[Technical Roadmap](reports/docs/references/technical_roadmap.md)** | Phased engineering execution plan (Phase 0 through Phase 7) with explicit exit criteria. |
| **[System Design & ADRs](reports/docs/architecture/system_design.md)** | Component topology, sequence flows, contract specifications, and Architectural Decision Records (ADR-001 to ADR-008). |
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
| **Experiment Tracking** | `uv run mlflow ui` | Launches local MLflow dashboard for model tracking. |
| **Docker Build & Run** | `docker compose up --build` | Builds and launches all services via Docker Compose. |

---

## 📄 License & Authors

- **Author:** Sebastián Garrido Arévalo
- **License:** [MIT License](LICENSE.txt)
