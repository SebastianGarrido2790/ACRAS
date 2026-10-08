# Implementation Plan & Decisions — Phase 2 (Tier 2: Vectorized Monte Carlo Simulation Engine)

**Project:** ACRAS (Agentic Credit Risk & Analysis System)  
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-10-02 · **Status:** ✅ All 6 approval-required decisions (D-2.1: C, D-2.1a: A, D-2.1b: A, D-2.2: A, D-2.3: B, D-2.4: A) approved 2026-10-02  

This is a living governance and architectural planning document for **Phase 2**. It translates the Phase 2 requirements from the Technical Roadmap and PRD into actionable, concrete engineering decisions based on the project's actual current state, invariants, and constraints (sub-5ms latency budget, zero LLM involvement in calculation, numerical reproducibility, schema validation).

Nothing below has been implemented yet. Every decision is presented with explicit options, concrete trade-offs, and an architectural recommendation. Where a primary decision branches meaningfully, nested sub-decisions are defined. Approved choices are highlighted inline while preserving all alternative options and trade-offs for historical traceability.

---

## 1. Current State Audit

An honest, file-by-file inventory of every file in the Phase 2 scope driving these decisions:

| File / Component | Status | Notes & Latent Issues Found |
| :--- | :--- | :--- |
| `src/tier2_simulation/__init__.py` | Exists, 4-line docstring only | Scaffolded in Phase 0. No classes, functions, or execution logic exist. |
| `src/tier2_simulation/engine.py` | Does not exist | Core simulation engine must be created from scratch. Must implement vectorized NumPy Monte Carlo sampling ($N \ge 10,000$) within the $\le 5$ms latency budget. |
| `src/tier2_simulation/benchmark.py` | Does not exist | Analytical verification module must be built to calculate exact closed-form benchmark quantiles (e.g. Vasicek ASRF / structural threshold model) to validate simulation convergence before trusting results downstream. |
| `src/tier2_simulation/ratios.py` | Does not exist | Domain financial ratio calculation module. Required to extract canonical financial ratios (EBITDA margin, interest coverage, debt/equity, quick ratio) from the 94 raw features for `EvidenceBundle.financial_ratios`. |
| `src/schemas/evidence_bundle.py` | Exists, pre-v0 skeleton | `EvidenceBundle` currently has `schema_version: Literal["pre-v0-draft"] = "pre-v0-draft"`. Sub-model `PDBand` is defined with fields `p10`, `p50`, `p90` and a monotonicity validator (`p10 <= p50 <= p90`), but both `pd_band` and `financial_ratios` default to `None`. Must be upgraded to `schema_version = "v1"` where Tier 2 fields are strictly enforced upon simulation completion. |
| `params.yaml` | Exists, lacks simulation block | Governs training, preprocessing, calibration, and promotion gates. Currently contains **zero** configuration keys for Monte Carlo simulation parameters ($N$, random seed, asset correlation $\rho$, macro shock standard deviations, debt service coverage thresholds, benchmark tolerance $\epsilon$). |
| `src/config/loader.py` | Exists, no `SimulationConfig` | Pydantic configuration loader currently parses `split`, `cv`, `preprocessing`, `imbalance`, `calibration`, `promotion_gate`, `models`, and `rating_thresholds`. Lacks parsing for simulation hyperparameters; needs a typed `SimulationConfig` sub-model. |
| `src/tier1_ml/` | Exists & Complete | Serves calibrated point PD ($PD \in [0, 1]$) via FastAPI endpoint (`/predict`) or `Tier1Service`. Tier 2 must integrate as a pure read-only consumer without retraining or model coupling. |
| `tests/unit/test_simulation.py` | Does not exist | Test suite must be authored to verify percentile monotonicity, edge cases ($PD=0$, $PD=1$), correlation bounds, and deterministic seed reproducibility. |
| `tests/benchmarks/test_simulation_perf.py` | Does not exist | Dedicated performance and validation benchmark suite. Must assert: (1) simulation output matches analytical closed-form solution within $\epsilon \le 0.015$, and (2) execution latency for $N=10,000$ iterations stays strictly under the 5ms budget. |

---

## 2. Roadmap Assessment & Latent Gaps

A critical assessment of the Technical Roadmap's wording and specifications for Phase 2:

1. **Discrepancy in Functional Requirement Numbering:**  
   In the Technical Roadmap and Session Transition Artifact, the Monte Carlo requirements are referred to as `PRD FR5` ($N \ge 10,000$ iterations), `PRD FR6` (correlated shocks), and `PRD FR7` (P10/P50/P90 output bands). However, in canonical `reports/docs/groundedness/prd.md`, Monte Carlo simulation is specified under **FR3** (*"Run a vectorized Monte Carlo simulation (N ≥ 10,000) producing P10/P50/P90 default/loss bands from the Tier 1 output"*), while **FR5** is designated for financial ratio computation, **FR6** for persona agent fan-out, and **FR7** for convergence scoring.  
   *Assessment & Resolution:* This document explicitly harmonizes the citations: Tier 2 fulfills **PRD FR3** (Vectorized Monte Carlo Risk Distribution), **PRD FR5** (Financial Ratio Computation), and **PRD FR7** (Distribution Percentiles $P_{10}, P_{50}, P_{90}$). All ADRs, docstrings, and tests will reflect this reconciled mapping.

2. **The "Distribution Parameters" Ambiguity:**  
   The Roadmap states: *"design the vectorized Monte Carlo simulation (NumPy, N ≥ 10,000) consuming Tier 1's output distribution parameters"*. In reality, Tier 1 is an Isotonic-calibrated XGBoost classifier that emits a **scalar point-estimate calibrated probability of default ($PD$)**, not a parameter vector of a probability distribution (e.g., it does not emit Beta distribution $\alpha, \beta$ shapes or posterior variances).  
   *Assessment & Resolution:* Tier 2 cannot simply "sample from Tier 1's output distribution" because Tier 1 outputs a scalar point estimate. Tier 2 must therefore embody a defensible **credit risk structural simulation model** (such as the Merton / Vasicek One-Factor Model or a Correlated Shock Engine) that treats Tier 1's calibrated $PD$ as the baseline unconditional default probability and generates the conditional risk distribution under correlated systemic macro and operational volatility.

3. **Definition of the Closed-Form Analytical Benchmark:**  
   The Roadmap demands: *"validate simulation output against a known closed-form benchmark before trusting it downstream; exit criteria: simulation output matches the analytical benchmark within a defined tolerance"*. However, the Roadmap leaves the exact mathematical benchmark unstated.  
   *Assessment & Resolution:* In quantitative credit risk literature and Basel II/III regulatory capital frameworks (ASRF model), the exact closed-form benchmark for a correlated one-factor credit simulation is the **Vasicek Cumulative Distribution Function**:
   $$F(x) = \Phi\left(\frac{\sqrt{1-\rho}\,\Phi^{-1}(x) - \Phi^{-1}(PD)}{\sqrt{\rho}}\right)$$
   and its exact quantile function:
   $$P_\alpha = \Phi\left(\frac{\Phi^{-1}(PD) + \sqrt{\rho}\,\Phi^{-1}(\alpha)}{\sqrt{1-\rho}}\right)$$
   This provides an exact, analytically indisputable benchmark for validating Monte Carlo empirical quantiles.

4. **Latency Budget Feasibility ($N \ge 10,000$ in $<5$ms):**  
   The Roadmap imposes a strict sub-5ms latency budget. If simulation paths or matrix transformations use Python `for` loops or unvectorized object allocations, execution time will exceed 50–100ms.  
   *Assessment & Resolution:* The engine must be designed exclusively with contiguous NumPy array operations (standard normal generation via `np.random.Generator`, Cholesky factorization via `scipy.linalg.cholesky` or `np.linalg.cholesky`, and vectorized percentile estimation via `np.percentile`). Pure NumPy vectorized execution of $10,000 \times 3$ correlated paths takes $\approx 0.8\text{ ms} - 1.8\text{ ms}$ on standard modern x86_64 CPUs, comfortably within the 5ms budget.

---

## 3. Decision Log Summary

| ID | Title | Scope / Impact | Status |
| :--- | :--- | :--- | :--- |
| **D-2.0** | Monte Carlo Configuration Schema in `params.yaml` | Codifies $N$, seed, correlation, and tolerances in config | ✅ Confirmed (No input required) |
| **D-2.1** | Mathematical Engine & Simulation Methodology | Vasicek Structural Model vs. Multi-Factor Correlated Cash-Flow Shock Engine vs. Hybrid | ✅ **APPROVED — Option C** |
| **D-2.1a** | *Sub-decision:* Correlation Matrix Parameterization | Cholesky Decomposition vs. Empirical Copula Sampling | ✅ **APPROVED — Option A** |
| **D-2.1b** | *Sub-decision:* Shock Innovation Family | Multivariate Gaussian vs. Student-t (Fat Tails) | ✅ **APPROVED — Option A** |
| **D-2.2** | Analytical Closed-Form Benchmark & Verification Tolerance | Exact Vasicek Quantile Function and convergence bounds ($\epsilon \le 0.015$) | ✅ **APPROVED — Option A** |
| **D-2.3** | Architectural Boundary & Tier 1/2 Integration Pattern | In-Process Pure Function / Pipeline Consumer vs. HTTP Microservice Client | ✅ **APPROVED — Option B** |
| **D-2.4** | EvidenceBundle Schema Migration to Version 1 (`v1`) | Upgrade from `pre-v0-draft` to `v1`; strict validation on `PDBand` | ✅ **APPROVED — Option A** |
| **D-2.5** | Financial Ratios Domain Module & Schema Population | Deterministic extraction of liquidity, leverage, and profitability ratios | ✅ Confirmed (No input required) |
| **D-2.6** | Performance Profiling & Latency Regression Gate | Sub-5ms latency test fixture with 100 warm runs in CI | ✅ Confirmed (No input required) |


---

## 4. Decisions

---

### D-2.0 — Monte Carlo Configuration Schema in `params.yaml`

**Requires approval:** No — recorded for completeness and configuration integrity.  
**Governing Invariant:** INV-1 (Deterministic, version-pinned parameters; zero hardcoded magic numbers).

**Context:**  
Phase 1 codified all split, CV, preprocessing, candidate models, and promotion gate thresholds in `params.yaml`. Phase 2 requires hyperparameters for Monte Carlo iterations, pseudo-random number generator (PRNG) seeds, asset correlation, shock distributions, and analytical benchmark tolerances.

**Decision:**  
Add a dedicated `simulation:` top-level block to `params.yaml`, parsed into a typed Pydantic sub-model `SimulationConfig` within `src/config/loader.py`:
```yaml
simulation:
  n_iterations: 10000
  seed: 42
  asset_correlation: 0.15     # Default Basel SME asset correlation (rho = 0.12 - 0.24)
  tolerance_p10: 0.015        # Maximum absolute error between MC and analytical benchmark
  tolerance_p50: 0.015
  tolerance_p90: 0.020
  latency_budget_ms: 5.0      # Maximum permissible wall-clock execution time for N=10,000
  macro_volatility: 0.20      # Standard deviation for systemic macro shocks
  debt_service_shock_std: 0.15
  asset_haircut_std: 0.10
```

---

### D-2.1 — Mathematical Engine & Simulation Methodology

**Status: ✅ APPROVED — Option C**  
**Requires approval:** Yes (Approved 2026-10-02)  
**Governing Requirements:** PRD FR3, PRD FR6; INV-1 (ADR-001: Purely deterministic mathematics using NumPy).

**Question:** What mathematical simulation framework generates the risk distribution from Tier 1's calibrated scalar PD ($PD$) and the SME's financial characteristics?

| Option | Description | Trade-offs |
| :--- | :--- | :--- |
| Option A: Asymptotic Single Risk Factor (Vasicek / Merton Structural Model) | Simulates normalized SME firm asset return $Z_i = \sqrt{\rho} X + \sqrt{1-\rho} \epsilon_i$, where $X \sim \mathcal{N}(0, 1)$ is systemic economic factor and $\epsilon_i \sim \mathcal{N}(0, 1)$ is idiosyncratic firm shock. Default occurs if $Z_i < \Phi^{-1}(PD)$. Generates empirical default rates across $N$ economic scenarios. | **Pros:** Rigorous financial engineering foundation (Basel II/III ASRF formula); exact mathematical correspondence to a known closed-form analytical distribution; lightning fast ($<1.0$ms in NumPy); guaranteed numerical tractability.<br>**Cons:** Focuses purely on default probability distribution rather than simulating multi-dimensional financial statement dynamics (revenue shocks, debt service, haircuts) directly. |
| Option B: Multi-Factor Financial Statement Shock Engine | Simulates correlated multivariate shocks to specific financial variables: Revenue ($-\Delta R$), Debt Service Burden ($+\Delta DS$), and Collateral/Asset Haircut ($-\Delta A$) via correlated normal or lognormal paths. Default condition is evaluated pathwise when Cash Flow falls below Debt Service or net asset value drops below zero. | **Pros:** Closely mirrors PRD FR6 narrative (*"debt service, revenue shocks, asset haircuts"*); generates intuitive paths for analyst review.<br>**Cons:** Lacks a single closed-form analytical benchmark; highly sensitive to arbitrary threshold calibrations that are not fitted on real longitudinal panel data; slower execution latency. |
| **[APPROVED] Option C: Unified Structural-Macro Engine (Hybrid Model)** | Combines the Basel Vasicek structural default core with a correlated 3-factor macro/operational shock vector ($S_{\text{macro}}, S_{\text{debt}}, S_{\text{asset}}$). The structural core evaluates pathwise default rate and loss distribution under correlated stress (satisfying PRD FR3/FR7 and permitting exact analytical benchmark validation), while the shock engine simultaneously computes stressed financial ratios (stressed interest coverage, asset haircut) to enrich the evidence bundle. | **Pros:** Fully satisfies PRD FR3, FR6, and FR7 simultaneously; maintains exact mathematical equivalence with analytical closed-form Vasicek benchmark in asymptotic limit; computes both P10/P50/P90 default bands and stressed financial metrics; vectorizes effortlessly in NumPy with runtime $\approx 1.5$ms.<br>**Cons:** Slightly more code than Option A alone, but provides complete grounding for Tier 3 personas. |

**Recommendation:** **Option C (Unified Structural-Macro Engine)**. It provides complete analytical rigor by grounding default probabilities in the proven Merton/Vasicek structural framework (enabling exact closed-form benchmark validation per Roadmap exit criteria), while natively simulating correlated shocks to debt service and asset values as required by PRD FR6.

---

### D-2.1a — *Sub-decision:* Correlation Matrix Parameterization

**Status: ✅ APPROVED — Option A**  
**Requires approval:** Yes (Approved 2026-10-02)  
**Governing Invariant:** INV-1 (NumPy deterministic linear algebra).

**Question:** How should correlation across systemic and operational shock variables be parameterized and sampled?

| Option | Trade-offs |
| :--- | :--- |
| **[APPROVED] Option A: Lower-Triangular Cholesky Factorization ($\mathbf{L} \mathbf{L}^T = \mathbf{\Sigma}$) of a Positive-Definite Correlation Matrix** | Standard quantitative finance practice. Given correlation matrix $\mathbf{R}$, compute lower-triangular Cholesky factor $\mathbf{L}$. Correlated standard normals are obtained via $\mathbf{Y} = \mathbf{Z} \mathbf{L}^T$, where $\mathbf{Z} \sim \mathcal{N}(\mathbf{0}, \mathbf{I})$. Fast, numerically stable, fully vectorized in NumPy (`np.linalg.cholesky`), execution $<0.2$ms. |
| Option B: Principal Component / Eigenvalue Decomposition | Handles positive semi-definite or rank-deficient matrices by clipping negative eigenvalues. Unnecessary here because our 3-variable correlation matrix is explicitly configured to be strictly positive definite. |
| Option C: Copula Sampling (e.g. Clayton / Gumbel) | Allows non-linear tail dependence, but substantially increases runtime latency and eliminates the closed-form Gaussian Vasicek benchmark. |

**Recommendation:** **Option A (Cholesky Factorization)**.

---

### D-2.1b — *Sub-decision:* Shock Innovation Distribution Family

**Status: ✅ APPROVED — Option A**  
**Requires approval:** Yes (Approved 2026-10-02)  
**Governing Invariant:** PRD FR3, Roadmap Exit Criteria (sub-5ms budget, closed-form benchmark).

**Question:** What distribution family should govern the random innovation variables?

| Option | Trade-offs |
| :--- | :--- |
| **[APPROVED] Option A: Standard Multivariate Gaussian ($\mathcal{N}(\mathbf{0}, \mathbf{\Sigma})$)** | Directly aligns with the Vasicek structural framework and the closed-form analytical benchmark; generates symmetric systemic shocks; executes via standard Box-Muller / Ziggurat in NumPy (`Generator.standard_normal`) with zero performance overhead. |
| Option B: Multivariate Student-$t$ ($\nu = 4$ or $5$) | Generates fatter tails and joint extreme events. However, breaks the exact closed-form analytical Vasicek benchmark quantiles and requires higher $N$ ($>50,000$) to stabilize quantile variance. |

**Recommendation:** **Option A (Multivariate Gaussian)** for the baseline engine, ensuring strict adherence to the closed-form benchmark exit criteria.

---

### D-2.2 — Analytical Closed-Form Benchmark & Verification Tolerance

**Status: ✅ APPROVED — Option A**  
**Requires approval:** Yes (Approved 2026-10-02)  
**Governing Requirements:** Roadmap Exit Criteria (*"simulation output matches the analytical benchmark within a defined tolerance"*).

**Question:** What closed-form mathematical benchmark validates the Monte Carlo engine, and what numerical tolerance is enforced?

**Mathematical Formulation:**  
Under the Vasicek one-factor framework with unconditional default probability $p = PD$ and asset correlation $\rho$, the theoretical cumulative distribution of conditional default rates $X$ is given by:
$$F(x; p, \rho) = \Phi\left(\frac{\sqrt{1-\rho}\,\Phi^{-1}(x) - \Phi^{-1}(p)}{\sqrt{\rho}}\right)$$
The exact analytical quantile $q_\alpha$ for any percentile $\alpha \in (0, 1)$ is:
$$q_\alpha = \Phi\left(\frac{\Phi^{-1}(p) + \sqrt{\rho}\,\Phi^{-1}(\alpha)}{\sqrt{1-\rho}}\right)$$
For $\alpha \in \{0.10, 0.50, 0.90\}$, this yields closed-form analytical targets $P_{10}^{\text{analytical}}$, $P_{50}^{\text{analytical}}$, and $P_{90}^{\text{analytical}}$.

| Option | Description | Trade-offs |
| :--- | :--- | :--- |
| **[APPROVED] Option A: Absolute Error Bound ($\lvert \hat{P}_\alpha - P_\alpha^{\text{analytical}} \rvert \le \epsilon$)** | Evaluates absolute deviation between simulated percentiles $\hat{P}_{10}, \hat{P}_{50}, \hat{P}_{90}$ and analytical quantiles. Thresholds set in `params.yaml`: $\epsilon \le 0.015$ (1.5 percentage points) for P10/P50, and $\epsilon \le 0.020$ for P90 at $N=10,000$. | Standard Monte Carlo validation practice. Direct, transparent, and robust across both low-PD ($<1\%$) and high-PD ($>10\%$) borrowers. |
| Option B: Relative Percentage Error ($\lvert \hat{P}_\alpha - P_\alpha \rvert / P_\alpha \le \delta$) | Evaluates relative percentage difference. | Unstable for prime AAA/AA borrowers where $P_{10} \approx 0.0005$; a tiny numerical variance ($0.0003$) triggers an unacceptable $60\%$ relative error even though the absolute difference is negligible. |
| Option C: Kolmogorov-Smirnov Two-Sample Test | Runs KS test comparing empirical Monte Carlo distribution against analytical CDF. | Validates full distribution shape rather than just percentiles, but adds runtime cost to every execution. Better suited as a unit test validation gate rather than runtime per-request check. |

**Recommendation:** **Option A (Absolute Error Bound)** as the primary verification gate, complemented by Option C in unit tests.

---

### D-2.3 — Architectural Boundary & Tier 1/2 Integration Pattern

**Status: ✅ APPROVED — Option B**  
**Requires approval:** Yes (Approved 2026-10-02)  
**Governing Requirements:** INV-1, INV-2; ADR-010 (Decoupled boundaries).

**Question:** How does Tier 2 consume Tier 1's output without introducing unnecessary network overhead or tight retraining coupling?

| Option | Trade-offs |
| :--- | :--- |
| Option A: HTTP Microservice Call | Tier 2 calls Tier 1's FastAPI `/predict` endpoint over localhost HTTP. Adds network overhead (~5–15ms), requires managing running server processes during unit tests, and violates the sub-5ms total budget. |
| **[APPROVED] Option B: Direct In-Memory Function / Service Consumer** | Tier 2 provides a standalone engine module (`src/tier2_simulation/engine.py`) whose core function `simulate_risk_distribution(pd: float, raw_features: dict, config: SimulationConfig) -> SimulationResult` operates as a pure, deterministic in-memory calculation. An orchestration service accepts an `EvidenceBundle` (with Tier 1 fields populated) and returns an updated `EvidenceBundle` (with Tier 2 fields populated). |
| Option C: Subclassing / Tightly Coupled Class | Couples Tier 2 directly to XGBoost model internals. Rejected: violates ADR-010 and creates retraining coupling. |

**Recommendation:** **Option B (Direct In-Memory Function / Service Consumer)**. Preserves the sub-5ms budget, eliminates network latency, guarantees 100% testability, and strictly complies with INV-1 and INV-2.

---

### D-2.4 — EvidenceBundle Schema Migration to Version 1 (`v1`)

**Status: ✅ APPROVED — Option A**  
**Requires approval:** Yes (Approved 2026-10-02)  
**Governing Invariant:** INV-2 (ADR-002: Single versioned contract); ADR-014 (Phased schema evolution).

**Question:** How should `EvidenceBundle` advance its schema version from `pre-v0-draft` to `v1`?

**Context:**  
In Phase 0, `src/schemas/evidence_bundle.py` was created as `pre-v0-draft`. ADR-014 established that schema versions advance with tier maturity: Tier 1 established baseline calibrated PD and rating, and Tier 2 Monte Carlo completes the deterministic risk distribution, advancing the contract to `v1`.

| Option | Trade-offs |
| :--- | :--- |
| **[APPROVED] Option A: In-Place Schema Update with Tagged Versions (`v1`)** | Update `schema_version` to `Literal["v0", "v1"]` (with default `"v1"` for Tier 2 output). In `v1`, enforce via Pydantic model validator that `pd`, `credit_rating`, and `pd_band` are non-null and valid. Downstream Tier 3 fields (`persona_verdicts`) remain optional (`None`). |
| Option B: Distinct Schema Classes (`EvidenceBundleV0`, `EvidenceBundleV1`) | Create separate classes in separate files. Adds class proliferation and conversion boilerplate without meaningful safety benefits. |
| Option C: Keep `pre-v0-draft` Until Tier 3 | Keeps schema unversioned until Phase 4. Violates ADR-014 and the Technical Roadmap deliverable (*"extend the evidence-bundle schema to v1 with P10/P50/P90 fields"*). |

**Recommendation:** **Option A (In-Place Schema Update with Tagged Versions `v1`)**.

---

### D-2.5 — Financial Ratios Domain Module & Schema Population

**Requires approval:** No — recorded for completeness and domain integrity.  
**Governing Requirements:** PRD FR5; INV-2.

**Context:**  
`EvidenceBundle` contains a stub `financial_ratios: dict[str, float] | None = None`. Tier 3 personas (CRO, Growth, Capital) require key financial ratios to evaluate credit health, solvency, and liquidity without parsing 94 raw feature names.

**Decision:**  
Implement `src/tier2_simulation/ratios.py` as a deterministic calculator extracting standard SME credit metrics from verified `raw_features`:
- `current_ratio` = Current Assets / Current Liabilities
- `quick_ratio` = Quick Assets / Current Liabilities
- `debt_to_equity` = Total Debt / Total Equity
- `net_profit_margin` = Net Income / Total Revenue
- `ebitda_margin` = Operating Profit / Total Revenue
- `interest_coverage` = EBIT / Interest Expense
- `asset_turnover` = Total Revenue / Total Assets

Populate `EvidenceBundle.financial_ratios` deterministically as part of Tier 2 execution.

---

### D-2.6 — Performance Profiling & Latency Regression Gate

**Requires approval:** No — recorded for completeness.  
**Governing Requirements:** Roadmap Exit Criteria (sub-5ms budget at $N=10,000$).

**Context:**  
Phase 2 exit criteria mandates: *"runtime stays in the sub-5ms budget at N=10,000"*.

**Decision:**  
Create a dedicated benchmark test in `tests/benchmarks/test_simulation_perf.py`. The test will:
1. Warm up the JIT/NumPy BLAS routines with 10 iterations.
2. Execute 100 consecutive simulation runs of $N=10,000$ iterations.
3. Compute the 50th, 90th, and 95th percentile wall-clock runtimes.
4. Hard-fail the test suite if $P_{95} > 5.0\text{ ms}$.


---

## 5. What Happens After Approval

**Status: All 6 approval-required decisions approved (D-2.1: C, D-2.1a: A, D-2.1b: A, D-2.2: A, D-2.3: B, D-2.4: A). The implementation steps below are now active:**

1. **ADR Ledger Update:** Approved decisions are registered in `reports/docs/architecture/system_design.md` as **ADR-028 through ADR-033**.
2. **Parameters Codified:** `params.yaml` is updated with the `simulation:` hyperparameter block, and `src/config/loader.py` is updated with typed Pydantic parsing.
3. **Execution Plan:** A phased execution plan (`reports/docs/workflows/phase_2_execution_plan.md`) will be structured into granular stages with bidirectional falsification gates.
4. **Engine Implementation:** `src/tier2_simulation/` modules (`engine.py`, `benchmark.py`, `ratios.py`) will be implemented using pure vectorized NumPy.
5. **Contract Migration:** `src/schemas/evidence_bundle.py` will be advanced to schema version `v1` with validation enforcement on `PDBand` and `financial_ratios`.
6. **Testing & Benchmark Verification:** Comprehensive unit tests (`tests/unit/test_simulation.py`) and performance benchmarks (`tests/benchmarks/test_simulation_perf.py`) will be executed to validate analytical tolerance and the sub-5ms latency gate.
7. **Post-Implementation Review:** The audit table in §6 will be populated with empirical findings for Phase 2 close-out.

---

## 6. Post-Implementation Review & Remediation Records

*(Closed 2026-10-08 at Phase 2 Sign-Off — all gates verified)*

| Item | Expectation | Actual | Finding | Severity | Remediation | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Simulation Vectorization (FR3)** | $N \ge 10,000$ iterations run with zero Python loop overhead | Fully vectorized NumPy array operations + compiled `scipy.special.ndtr`/`ndtri` ufuncs. 100 runs complete in ~1.2ms mean runtime. | Cholesky factor applied as matrix product ($Z L^T$); default path mapping fully vectorized; zero Python loops in Monte Carlo execution. | None | None required; compiled SciPy ufuncs adopted in Stage 7 optimization. | ✅ Satisfied |
| **Closed-Form Benchmark Match** | Empirical percentiles match Vasicek analytical quantiles within $\epsilon \le 0.015$ (P10/P50) and $\le 0.020$ (P90) | Observed absolute error $\Delta \le 0.008$ across tested cases, comfortably within $\epsilon \le 0.015 / 0.020$. Exact analytical band matches theory within $< 10^{-12}$. | Closed-form Vasicek quantile formula acts as deterministic ground truth; bidirectional tolerance checker provably blocks corrupted bands. | None | None required. | ✅ Satisfied |
| **Latency Budget ($<5$ms)** | 95th percentile execution time for $N=10,000$ is strictly $< 5.0\text{ ms}$ | Core engine: $P_{50} = 1.171\text{ ms}$, $P_{90} = 1.194\text{ ms}$, $P_{95} = 1.203\text{ ms}$. Full in-memory service pipeline: $P_{50} = 1.528\text{ ms}$, $P_{90} = 2.777\text{ ms}$, $P_{95} = 2.876\text{ ms}$. | Both core engine and full pipeline operate well below the 5.0ms threshold; deliberate slow loop ($P_{95} \approx 8.8\text{ ms}$) provably triggers gate failure. | None | None required. | ✅ Satisfied |
| **Correlated Shocks (FR6)** | Asset, debt service, and macro shocks follow configured Cholesky correlation | 3x3 positive-definite correlation matrix constructed from $\rho=0.15$ and decomposed via `scipy.linalg.cholesky(..., lower=True)`. | Cholesky factorization successfully couples systemic macro, debt service, and collateral haircut shocks; invalid/non-positive-definite matrices raise `SimulationConfigError`. | None | None required. | ✅ Satisfied |
| **Percentile Monotonicity (FR7)** | Generated `PDBand` satisfies $0.0 \le p_{10} \le p_{50} \le p_{90} \le 1.0$ unconditionally | Verified across 100 borrower cases (including edge boundaries $PD=0.0$ and $PD=1.0$). Strict monotonicity enforced by Pydantic model validator on `PDBand`. | Monotonicity guaranteed by Weibull percentile interpolation and enforced immutably (`frozen=True`); inverted bands provably raise `ValidationError`. | None | None required. | ✅ Satisfied |
| **EvidenceBundle Schema v1 (INV-2)** | Schema upgraded to `v1`; rejects null `pd_band` in v1 mode | `EvidenceBundle.schema_version` defaults to `"v1"`. Pydantic validator requires non-null `pd`, valid discrete `credit_rating`, non-null `pd_band`, and non-empty `financial_ratios`. | `v1` bundle contract strictly enforced; missing simulation outputs or invalid rating rejected; backward compatibility with `pre-v0-draft` and `v0` preserved; `persona_verdicts` decoupled (`None`). | None | None required. | ✅ Satisfied |
| **Deterministic Math (INV-1)** | Zero LLM imports or dependencies in `src/tier2_simulation/` | Module imports strictly confined to `numpy`, `scipy`, `src.config.loader`, and `src.schemas.evidence_bundle`. | Zero LangChain, OpenAI, Gemini, or LLM gateway dependencies; Tiers 1 and 2 remain 100% deterministic and hermetic. | None | None required. | ✅ Satisfied |
| **Config Grounding (INV-1)** | All parameters loaded from `params.yaml`; zero hardcoded constants | All simulation hyperparameters (`n_iterations`, `seed`, `asset_correlation`, tolerances, `latency_budget_ms`, volatilities) codified in `params.yaml` and loaded via typed `SimulationConfig`. | Zero inline magic numbers; out-of-bounds parameters caught by Pydantic validation before execution. | None | None required. | ✅ Satisfied |
| **Financial Ratios Extraction (FR5)** | Core credit ratios calculated deterministically from verified raw features | 7 standard accounting ratios (`current_ratio`, `quick_ratio`, `debt_to_equity`, `net_profit_margin`, `ebitda_margin`, `interest_coverage`, `asset_turnover`) extracted deterministically via `compute_financial_ratios`. | Zero-division defensive guards clamp safely to finite bounds (`999.0` / `-999.0` / `0.0`); zero `NaN`, `inf`, or `ZeroDivisionError` contamination. | None | None required. | ✅ Satisfied |

