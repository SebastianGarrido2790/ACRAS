# Phase 2 — Staged Execution Plan (Tier 2: Vectorized Monte Carlo Simulation Engine)

**Project:** ACRAS (Agentic Credit Risk & Analysis System)  
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-10-02 · **Status:** Sequencing only — preconditions satisfied (all Phase 2 decisions approved 2026-10-02), implementation ready to proceed  
**Key References:** [Phase 2 Implementation Plan](../decisions/phase_2_implementation_plan.md), and [Technical Roadmap](../groundedness/technical_roadmap.md)  

Same discipline as Phase 0 and Phase 1: nothing here is code, ADRs are assigned strictly to the stage where the underlying architectural fact actually gets built or verified, and falsification is applied selectively — where a stage's gate is a real programmatic check worth deliberately breaking once to prove test sensitivity, not uniformly as a rubber stamp.

**Precondition status:** **Satisfied** — All 6 approval-required decisions (D-2.1: Option C, D-2.1a: Option A, D-2.1b: Option A, D-2.2: Option A, D-2.3: Option B, D-2.4: Option A) and confirmed decisions (D-2.0, D-2.5, D-2.6) are locked in `reports/docs/decisions/phase_2_implementation_plan.md`.

---

## Stage Index

| Stage | Name | Gate (one line) | Falsification |
| :--- | :--- | :--- | :--- |
| **0** | Pre-Implementation Verification & Dependency Check | Every checklist item confirmed true; working tree clean | N/A — verification checklist |
| **1** | Simulation Configuration & Parameters Pipeline | `params.yaml` parsed cleanly into typed `SimulationConfig`; out-of-bounds rejected | Yes — invalid parameter injection |
| **2** | Analytical Benchmark Module (Vasicek Closed-Form) | Closed-form benchmark computes exact theoretical quantiles; tolerance gate blocks bad inputs | Yes — both directions on synthetic quantiles |
| **3** | Vectorized Monte Carlo Engine (Core) | $N \ge 10,000$ paths execute via Cholesky; empirical quantiles match analytical benchmark within $\epsilon$ | Yes — broken correlation matrix & seed check |
| **4** | Domain Financial Ratios Extraction Module | Core SME ratios extracted deterministically; zero-division safely handled | Yes — zero-denominator edge cases |
| **5** | EvidenceBundle Schema Migration to Version 1 (`v1`) | Schema v1 enforces non-null `pd_band` and monotonic percentiles | Yes — null `pd_band` & inverted monotonicity |
| **6** | Tier 1/Tier 2 In-Memory Orchestration Service | In-memory service accepts Tier 1 bundle, enriches with Tier 2 outputs, and returns valid v1 bundle | Yes — missing required Tier 1 fields |
| **7** | Performance Benchmark & Latency Gate | $P_{95}$ execution time for $N=10,000$ is strictly $< 5.0\text{ ms}$ over 100 warm iterations | Yes — deliberate unvectorized loop slowdown |
| **8** | Comprehensive Automated Test Suite | All falsifications formalized into permanent unit/perf regression tests | N/A — formalizes Stages 1–7 falsifications |
| **9** | ADR Consolidation & Phase 2 Sign-Off | PIR fully populated; ADR-028–ADR-033 filed in `system_design.md`; exit criteria verified both directions | N/A — documentation audit against reality |

---

## Stage 0 — Pre-Implementation Verification & Dependency Check ✅ **PASSED**

**Goal:** Confirm the workspace, dependencies, and Phase 1 artifacts are in a known, stable state before any Phase 2 implementation begins.

**Checklist:**
- [x] Working tree is clean on `main` branch (`git status`).
- [x] Virtual environment dependencies (`uv run pytest`, `uv run ruff check .`, `uv run pyright`) pass with 0 errors.
- [x] Phase 1 model artifact exists and loads correctly (`artifacts/promoted_model_bundle.joblib`).
- [x] `src/tier2_simulation/__init__.py` is present as an empty scaffold.
- [x] All Phase 2 architectural decisions (D-2.0 through D-2.6) are marked Approved in `phase_2_implementation_plan.md`.

**ADR Implements:** None new.

**Falsification:** Not applicable — verification checklist.

**Gate 0:** All checklist items confirmed true; baseline environment fully verified.

---

## Stage 1 — Simulation Configuration & Parameters Pipeline ✅ **PASSED**

**Goal:** Codify Monte Carlo simulation hyperparameters into `params.yaml` (D-2.0) and implement typed Pydantic loading in `src/config/loader.py` to prevent hardcoded magic numbers (INV-1).

**Actions:**
- Add top-level `simulation:` block to `params.yaml` specifying `n_iterations: 10000`, `seed: 42`, `asset_correlation: 0.15`, `tolerance_p10: 0.015`, `tolerance_p50: 0.015`, `tolerance_p90: 0.020`, `latency_budget_ms: 5.0`, `macro_volatility: 0.20`, `debt_service_shock_std: 0.15`, and `asset_haircut_std: 0.10`.
- Create `SimulationConfig` Pydantic model with strict field validation (`ge`, `le`, `extra="forbid"`) in `src/config/loader.py`.
- Integrate `SimulationConfig` into `AppConfig` and expose via `load_params()`.
- Add unit test in `tests/unit/test_config.py` verifying parsing and default values.

**ADR Implements:** **ADR-028** (Simulation Configuration & Reproducibility Parameters).

**Falsification:** Inject an invalid configuration parameter (e.g. `asset_correlation: 1.5` or `n_iterations: -100`) and verify that `load_params()` immediately raises a Pydantic `ValidationError` rather than silently propagating invalid bounds downstream.

**Gate 1:** `params.yaml` parsed cleanly into typed `SimulationConfig`; deliberate invalid configuration provably blocked by Pydantic validation.

---

## Stage 2 — Analytical Benchmark Module (Vasicek Closed-Form) ✅ **PASSED**

**Goal:** Author the closed-form Vasicek analytical verification benchmark in `src/tier2_simulation/benchmark.py` (D-2.2) to establish the mathematical truth against which the Monte Carlo simulation will be validated.

**Actions:**
- Implement `vasicek_quantile(p: float, rho: float, alpha: float) -> float` computing the exact theoretical quantile:
  $$q_\alpha = \Phi\left(\frac{\Phi^{-1}(p) + \sqrt{\rho}\,\Phi^{-1}(\alpha)}{\sqrt{1-\rho}}\right)$$
  using `scipy.stats.norm.ppf` and `scipy.stats.norm.cdf`.
- Implement `vasicek_pdf(x: float, p: float, rho: float) -> float` and `vasicek_cdf(x: float, p: float, rho: float) -> float` for theoretical distribution evaluation.
- Implement standalone verification function `verify_simulation_benchmark(simulated_band: dict[str, float], p: float, rho: float, tolerances: dict[str, float]) -> tuple[bool, dict[str, float]]` computing absolute error $\lvert \hat{P}_\alpha - P_\alpha^{\text{analytical}} \rvert$ and asserting $\le \epsilon$.
- Add unit tests validating analytical quantiles against published Basel II ASRF tables for standard credit portfolios.

**ADR Implements:** **ADR-030** (Closed-Form Vasicek Analytical Verification Benchmark).

**Falsification:** Test the verification function in both directions:
1. Provide an exact analytical band — confirm it passes cleanly (`is_valid == True`).
2. Provide a deliberately corrupted simulated band (e.g. perturbing $\hat{P}_{90}$ by $+0.05$, exceeding the 0.020 tolerance) — confirm it explicitly fails (`is_valid == False`) and reports the violating delta.

**Gate 2:** Analytical benchmark module is pure, deterministic, and unit-tested; bidirectional synthetic falsification demonstrates tolerance gate sensitivity.

---

## Stage 3 — Vectorized Monte Carlo Engine (Core) ✅ **PASSED**

**Goal:** Implement the pure vectorized NumPy Monte Carlo engine in `src/tier2_simulation/engine.py` (D-2.1, D-2.1a, D-2.1b) executing $N \ge 10,000$ iterations within the sub-5ms latency budget.

**Actions:**
- Define 3-variable correlation matrix $\mathbf{\Sigma}$ connecting systemic macro risk, debt service coverage shocks, and collateral asset haircuts.
- Compute lower-triangular Cholesky factor $\mathbf{L} = \text{cholesky}(\mathbf{\Sigma})$ using `scipy.linalg.cholesky(..., lower=True)`.
- Generate standard normal innovation matrix $\mathbf{Z} \in \mathbb{R}^{N \times 3}$ using `np.random.default_rng(seed).standard_normal((N, 3))`.
- Transform innovations into correlated paths $\mathbf{Y} = \mathbf{Z} \mathbf{L}^T$.
- Implement the Vasicek structural asset return path:
  $$Z_i = \sqrt{\rho} X + \sqrt{1-\rho} \epsilon_i$$
  where default condition is $Z_i < \Phi^{-1}(PD)$.
- Vectorize empirical quantile calculation across the $N$ paths using `np.percentile(..., [10, 50, 90], method="weibull")` to obtain $\hat{P}_{10}, \hat{P}_{50}, \hat{P}_{90}$.
- Enforce strict percentile monotonicity: $0.0 \le \hat{P}_{10} \le \hat{P}_{50} \le \hat{P}_{90} \le 1.0$.

**ADR Implements:** **ADR-029** (Unified Vasicek Structural & Correlated Macro-Shock Engine).

**Falsification:** 
1. Deterministic seed check: run two independent executions with identical seed; confirm simulated percentiles match to machine precision ($0.0$ difference). Alter seed; confirm values vary within stochastic bounds.
2. Degenerate input check: run with $PD=0.0$ (confirm $P_{10}=P_{50}=P_{90}=0.0$) and $PD=1.0$ (confirm $P_{10}=P_{50}=P_{90}=1.0$).
3. Correlation matrix defect: pass a non-positive-definite correlation matrix and verify engine catches `LinAlgError` and raises a typed domain exception (`SimulationConfigError`).

**Gate 3:** Core simulation engine executes $N=10,000$ paths; outputs match analytical benchmark within configured tolerances ($\epsilon \le 0.015 / 0.020$); all three falsifications pass.

---

## Stage 4 — Domain Financial Ratios Extraction Module ✅ **PASSED**

**Goal:** Implement `src/tier2_simulation/ratios.py` (D-2.5) to deterministically extract domain credit ratios from verified `raw_features` for downstream persona consumption (PRD FR5).

**Actions:**
- Implement pure function `compute_financial_ratios(raw_features: dict[str, float | int]) -> dict[str, float]`.
- Map canonical raw feature names to standardized credit metrics:
  - `current_ratio`: Current Assets / Current Liabilities
  - `quick_ratio`: Quick Assets / Current Liabilities
  - `debt_to_equity`: Total Debt / Total Equity
  - `net_profit_margin`: Net Income / Total Revenue
  - `ebitda_margin`: Operating Profit / Total Revenue
  - `interest_coverage`: EBIT / Interest Expense
  - `asset_turnover`: Total Revenue / Total Assets
- Implement zero-division defensive guards (clamping to finite domain bounds or fallback values e.g. 999.0 / -999.0 for coverage ratios) to guarantee zero `ZeroDivisionError` or `NaN` outputs.

**ADR Implements:** **ADR-033** (Deterministic Financial Ratio Extraction Module).

**Falsification:** Feed edge-case financial feature dictionaries with: (1) Current Liabilities = 0.0, and (2) Interest Expense = 0.0. Confirm the calculator returns safe, finite clamped values without raising uncaught Python exceptions or emitting `NaN`/`inf`.

**Gate 4:** All 7 financial ratios extracted accurately against test fixtures; zero-division edge cases handled defensively with zero `NaN` contamination.


---

## Stage 5 — EvidenceBundle Schema Migration to Version 1 (`v1`) ✅ **PASSED**

**Goal:** Advance `src/schemas/evidence_bundle.py` (D-2.4) from `pre-v0-draft` to `schema_version = "v1"`, enforcing strict validation on Tier 1 and Tier 2 outputs while keeping downstream Tier 3 fields decoupled.

**Actions:**
- Update `schema_version` type annotation in `EvidenceBundle` to `Literal["pre-v0-draft", "v0", "v1"]` with default `"v1"` for all Tier 2 outputs.
- Add Pydantic model validator verifying that when `schema_version == "v1"`:
  1. `pd` is not None and within $[0.0, 1.0]$.
  2. `credit_rating` is not None and matches valid rating categories (`AAA` through `CCC/C`).
  3. `pd_band` is not None and is an instance of `PDBand`.
  4. `financial_ratios` is not None and contains non-empty mapping of float ratios.
- Ensure `PDBand` monotonicity validator (`p10 <= p50 <= p90`) remains strictly active and immutable (`frozen=True`, `extra="forbid"`).
- Retain `persona_verdicts = None` as valid for `v1`, preserving tier boundary independence until Phase 4.

**ADR Implements:** **ADR-032** (EvidenceBundle Schema v1 Migration & PDBand Enforcement).

**Falsification:** Two probes against schema validation:
1. Attempt to instantiate `EvidenceBundle(schema_version="v1", pd=0.032, credit_rating="BB", pd_band=None)` — confirm Pydantic raises `ValidationError` for missing `pd_band`.
2. Attempt to instantiate `PDBand(p10=0.05, p50=0.02, p90=0.10)` — confirm Pydantic raises `ValueError` ("Percentiles must satisfy p10 <= p50 <= p90").

**Gate 5:** `EvidenceBundle` advances to `v1`; missing simulation outputs and non-monotonic percentiles are strictly blocked by Pydantic validation.

---

## Stage 6 — Tier 1/Tier 2 In-Memory Orchestration Service

**Goal:** Implement `src/tier2_simulation/service.py` (D-2.3) providing the decoupled in-memory integration pattern connecting Tier 1 outputs to Tier 2 simulation.

**Actions:**
- Implement `Tier2SimulationService` (or pure functional orchestration runner `run_simulation_pipeline(bundle: EvidenceBundle, config: SimulationConfig) -> EvidenceBundle`).
- Verify input `EvidenceBundle` contains valid Tier 1 `pd` and canonical `raw_features`.
- Invoke `src/tier2_simulation/engine.py` to generate the Monte Carlo risk distribution and `PDBand`.
- Invoke `src/tier2_simulation/ratios.py` to extract domain financial ratios.
- Return a new, immutable `EvidenceBundle` updated with `schema_version="v1"`, `pd_band`, and `financial_ratios`.
- Confirm zero network calls (HTTP microservice rejected per D-2.3) and zero model retraining dependencies (ADR-010).

**ADR Implements:** **ADR-031** (Tier 1/Tier 2 In-Memory Decoupled Integration Pattern).

**Falsification:** Pass an invalid/incomplete bundle (e.g. missing `pd` or empty `raw_features`) to `Tier2SimulationService`. Confirm the service halts with an informative domain error (`InvalidTier1InputError`) before attempting any matrix operations.

**Gate 6:** Clean end-to-end pipeline execution from Tier 1 inputs to a verified v1 `EvidenceBundle`; zero network overhead; malformed inputs gracefully rejected.

---

## Stage 7 — Performance Benchmark & Latency Gate

**Goal:** Author a dedicated performance test in `tests/benchmarks/test_simulation_perf.py` (D-2.6) enforcing the sub-5ms latency budget at $N=10,000$ iterations.

**Actions:**
- Author benchmark test utilizing `time.perf_counter_ns()`.
- Execute 10 warm-up runs to stabilize JIT/NumPy BLAS threads.
- Execute 100 timed simulation runs of $N=10,000$ iterations.
- Calculate 50th, 90th, and 95th percentile wall-clock latencies.
- Enforce hard assertion: $P_{95} < 5.0\text{ ms}$.
- Log timing summary to test report for auditability.

**ADR Implements:** None new — enforces Roadmap Exit Criteria and D-2.6.

**Falsification:** Introduce a deliberate unvectorized Python loop (`for _ in range(10000): ...`) inside a mock simulation path. Confirm the benchmark test fails immediately with an informative assertion failure stating execution exceeded the 5.0ms threshold.

**Gate 7:** Vectorized engine passes performance benchmark with $P_{95} < 5.0\text{ ms}$; deliberate slow loop provably triggers gate failure.


---

## Stage 8 — Comprehensive Automated Test Suite

**Goal:** Formalize every falsification performed in Stages 1–7 into permanent, automated unit and integration tests.

**Actions:**
- Implement `tests/unit/test_simulation.py`:
  - `test_simulation_config_validation`: asserts out-of-bound parameters raise `ValidationError`.
  - `test_vasicek_closed_form_quantiles`: asserts theoretical quantiles match known analytical values.
  - `test_benchmark_tolerance_checker_both_directions`: asserts tolerance function passes valid bands and blocks perturbed bands.
  - `test_monte_carlo_engine_seed_reproducibility`: asserts bit-for-bit identical outputs for identical seeds.
  - `test_monte_carlo_percentile_monotonicity`: asserts $0.0 \le P_{10} \le P_{50} \le P_{90} \le 1.0$ across 100 random borrower cases.
  - `test_financial_ratios_extraction`: asserts 7 credit ratios compute accurately and zero denominators clamp safely without `NaN`.
  - `test_evidence_bundle_v1_contract`: asserts v1 bundle requires non-null Tier 1 and Tier 2 outputs.
  - `test_tier2_service_end_to_end`: asserts in-memory execution from Tier 1 bundle to v1 bundle.
- Implement `tests/benchmarks/test_simulation_perf.py` running the 100-iteration latency check.
- Run complete test suite and code quality checks.

**ADR Implements:** None new — formalizes all Phase 2 decisions into permanent regression protection.

**Falsification:** Not applicable as a separate step — this stage formalizes Stages 1–7's falsifications into permanent automated test code.

**Gate 8:** Full test suite passes (`uv run pytest`); Ruff passes with 0 errors (`uv run ruff check .`); Pyright passes with 0 errors (`uv run pyright`).

---

## Stage 9 — ADR Consolidation & Phase 2 Sign-Off

**Goal:** Close the governance loop between "decided," "built," and "recorded" before Phase 3 is allowed to begin.

**Actions:**
- Confirm **ADR-028 through ADR-033** are filed in `reports/docs/architecture/system_design.md` with full context, decisions, and consequences:
  - **ADR-028:** Simulation Configuration & Reproducibility Parameters (D-2.0).
  - **ADR-029:** Unified Vasicek Structural & Correlated Macro-Shock Engine (D-2.1, D-2.1a, D-2.1b).
  - **ADR-030:** Closed-Form Vasicek Analytical Verification Benchmark (D-2.2).
  - **ADR-031:** Tier 1/Tier 2 In-Memory Decoupled Integration Pattern (D-2.3).
  - **ADR-032:** EvidenceBundle Schema v1 Migration & PDBand Enforcement (D-2.4).
  - **ADR-033:** Deterministic Financial Ratio Extraction Module (D-2.5).
- Update `reports/docs/architecture/system_design.md` §2 Current Implementation Status table: Phase 2 moves from "Not started" to **Complete**.
- Fill in every row of `reports/docs/decisions/phase_2_implementation_plan.md`'s Post-Implementation Review table (§6) with empirical findings, actual metrics, and confirmed test outputs.
- Independently re-verify the Roadmap's Phase 2 exit criteria in both directions:
  1. Simulated output matches the analytical benchmark within defined tolerances ($\le 0.015 / 0.020$).
  2. Runtime stays strictly under the 5.0ms budget at $N=10,000$.

**ADR Implements:** None new — verifies documentation completeness against reality.

**Falsification:** Not applicable — documentation and ledger audit against reality.

**Gate 9 (Phase 2 complete; Phase 3 may begin):** Every PIR row populated with real empirical numbers; `system_design.md` updated and cross-referenced; ADR-028 through ADR-033 registered; Roadmap Phase 2 exit criteria demonstrated in both directions.

---

## Summary Table

| Stage | Name | Primary Deliverable | ADR Implements | Gate Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **0** | Pre-Implementation Verification | Workspace & dependency audit | None | Clean git tree; all dependencies green; Phase 1 artifact loaded |
| **1** | Simulation Configuration Pipeline | `params.yaml` & `SimulationConfig` | **ADR-028** | Parameters parsed cleanly; invalid values blocked by Pydantic |
| **2** | Analytical Benchmark Module | `src/tier2_simulation/benchmark.py` | **ADR-030** | Exact Vasicek quantiles match theory; tolerance checker blocks corrupted bands |
| **3** | Vectorized Monte Carlo Engine | `src/tier2_simulation/engine.py` | **ADR-029** | $N=10,000$ paths run via Cholesky; quantiles match benchmark within $\epsilon$ |
| **4** | Domain Financial Ratios Module | `src/tier2_simulation/ratios.py` | **ADR-033** | 7 domain ratios extracted; zero-denominator cases safely clamped |
| **5** | EvidenceBundle Schema Migration | `src/schemas/evidence_bundle.py` | **ADR-032** | Schema v1 enforces non-null `pd_band` and monotonic percentiles |
| **6** | In-Memory Orchestration Service | `src/tier2_simulation/service.py` | **ADR-031** | Clean in-memory pipeline: Tier 1 bundle -> valid v1 bundle |
| **7** | Performance Benchmark Gate | `tests/benchmarks/test_simulation_perf.py` | None | $P_{95} < 5.0\text{ ms}$ at $N=10,000$; slow loop falsification fails gate |
| **8** | Automated Test Suite | `tests/unit/test_simulation.py` | None | Full test suite passes; Ruff and Pyright pass with 0 errors |
| **9** | ADR Consolidation & Sign-Off | PIR table & `system_design.md` update | None | All PIR rows populated; ADR-028–ADR-033 filed; Phase 2 exit criteria validated |

