# Wave A · W-A7 Evidence Report — Dataset→Ratio Trace & Tier 2 Parameter Sensitivity

*ACRAS · 2026-10-23 · Wave A (characterization only; no input guard, no engine change).*
*Source: [`execution_plan.md`](execution_plan.md) §2 W-A7 · authority: `remediation_plan.md` §4 R-01 / R-09 / D-01 / D-10.*

## 1. Result summary

| Item | Result |
| --- | --- |
| Raw benchmark row → `compute_financial_ratios` | **7 ratios, all 0.0** (no exception) |
| Accounting-input dict → same function | 7 correct non-zero ratios |
| Dataset-feature ↔ required-input alias matches | **0** (empty intersection) |
| Unused shock params ×10 (macro ×5) effect | **exactly zero** (dead config) |
| `asset_correlation` 0.05→0.30 | P10–P90 width **0.0435 → 0.1290** (~3×) |
| Characterization test | **4 passing** (`tests/unit/test_tier2_sensitivity.py`) |

The mismatch is an **input-contract defect**, not a ratio-arithmetic defect: the extractor is correct given accounting amounts, but the 94 benchmark columns are ratio-like, so every lookup falls back to `0.0`. Of the Tier 2 shock parameters, only `asset_correlation` is live; the three shock stds are parsed and validated but never consumed.

## 2. Dataset→ratio trace (R-01)

`compute_financial_ratios` derives 7 ratios from 11 accounting input groups. The dataset exposes 94 ratio-like features; **no normalized dataset name matches any required alias**.

| Output ratio | Required inputs (alias-normalized) |
| --- | --- |
| `current_ratio` | current_assets ÷ current_liabilities |
| `quick_ratio` | quick_assets ÷ current_liabilities |
| `debt_to_equity` | total_debt ÷ total_equity |
| `net_profit_margin` | net_income ÷ total_revenue |
| `ebitda_margin` | operating_profit ÷ total_revenue |
| `interest_coverage` | ebit ÷ interest_expense |
| `asset_turnover` | total_revenue ÷ total_assets |

**Why zero:** the dataset columns that look related are *outputs* of analogous ratios, not the accounting amounts the function expects — e.g. ` Current Ratio`, ` Quick Ratio`, ` Total debt/Total net worth`, ` Net Income to Total Assets`, ` Interest Coverage Ratio (…)`. Normalized aliases (`currentassets`, `totalrevenue`, `totalassets`, …) never occur as dataset keys, so `_lookup` returns `0.0` for every input and `_safe_ratio(0, 0)` returns `0.0`.

**Evidence:**
- raw row → `{current_ratio: 0.0, quick_ratio: 0.0, debt_to_equity: 0.0, net_profit_margin: 0.0, ebitda_margin: 0.0, interest_coverage: 0.0, asset_turnover: 0.0}`
- accounting dict → `{current_ratio: 2.0, quick_ratio: 1.6, debt_to_equity: 0.667, net_profit_margin: 0.05, ebitda_margin: 0.15, interest_coverage: 5.0, asset_turnover: 0.5}`

**Scope note:** this is characterization. The required-input guard (fail loudly instead of emitting seven zeros) is **deferred to post-Wave-A** per the approved plan; the characterization test explicitly does **not** assert a `ValueError`.

## 3. Unused shock parameters (R-09)

`SimulationConfig` validates `macro_volatility`, `debt_service_shock_std`, `asset_haircut_std`, but `run_monte_carlo_simulation` consumes only `asset_correlation`, `n_iterations`, and `seed`.

| Config | macro_volatility | debt_service_shock_std | asset_haircut_std | P10 | P50 | P90 |
| --- | --- | --- | --- | --- | --- | --- |
| base | 0.20 | 0.15 | 0.10 | 0.012595418 | 0.037507768 | 0.094382722 |
| perturbed | 1.00 (5×) | 1.50 (10×) | 1.00 (10×) | 0.012595418 | 0.037507768 | 0.094382722 |

Identical to all printed digits → the three shock parameters are **dead config** (proven by perturbation, not by inspection alone). `macro_volatility` cannot be 10×'d within its validated `le=1.0` bound, so its maximum (1.0, 5×) is used; that still proves zero effect.

## 4. `asset_correlation` sensitivity (R-09)

Fixed `pd = 0.05`, `n_iterations = 10,000`, seed 42.

| ρ | P10 | P50 | P90 | Width (P90−P10) |
| --- | --- | --- | --- | --- |
| 0.05 | 0.028346 | 0.046050 | 0.071895 | 0.043549 |
| 0.10 | 0.019117 | 0.041819 | 0.082985 | 0.063868 |
| 0.15 | 0.012595 | 0.037508 | 0.094383 | 0.081787 |
| 0.20 | 0.007981 | 0.033331 | 0.105109 | 0.097128 |
| 0.25 | 0.004770 | 0.029298 | 0.118105 | 0.113336 |
| 0.30 | 0.002700 | 0.025449 | 0.131658 | 0.128958 |

Observations:
- Band width grows **monotonically** (~3× from ρ=0.05 to 0.30); P90 rises 0.072→0.132 while P10 falls 0.028→0.003.
- P50 falls as ρ rises (the structural-correlation blend lowers the median while fattening both tails).
- `asset_correlation` is therefore a first-order, live knob; the configured 0.15 is mid-range and materially changes the band.

## 5. Characterization test (deliverable)

`tests/unit/test_tier2_sensitivity.py` (4 tests, 4 passing):

1. `test_raw_dataset_row_yields_seven_zero_ratios` — pins the seven-zeros behavior; asserts no exception (guard absent). Skips if the dataset is absent.
2. `test_accounting_inputs_produce_nonzero_ratios` — isolates the defect to the input contract.
3. `test_unused_shock_parameters_have_zero_effect` — base vs ×10-perturbed band identical.
4. `test_asset_correlation_sweep_widens_band` — monotone widening + `P10 ≤ P50 ≤ P90`.

## 6. Options recorded (not applied)

- **A — Input guard:** fail loudly on missing required accounting inputs instead of returning seven zeros. Deferred to post-Wave-A (explicitly out of W-A7 scope).
- **B — Deterministic dataset→ratio mapping:** map semantically valid dataset ratio columns (e.g. ` Current Ratio` → `current_ratio`) instead of recomputing from amounts. A contract change requiring owner approval (R-01/D-01).
- **C — Structured-profile inputs:** require the PRD's synthetic company profile with accounting amounts for ratio extraction; use raw rows only for model features. Aligns with the W-A2 provenance table.

No option is authorized by this characterization; the engine and config are unchanged.

## 7. Open items

1. The three dead shock keys should not be presented as active sensitivity controls; either wire them or remove/mark them in a change-managed config edit (R-09).
2. The input guard (Option A) must precede any raw-row → Tier 2 → Tier 3 demo path; otherwise the evidence bundle carries seven spurious zeros.
