# Wave A · W-A6 Evidence Report — Feature Quality & Yeo-Johnson λ / Range Audit

*ACRAS · 2026-10-23 · Wave A (read-only audit; no feature removal, no transform change).*
*Source: [`execution_plan.md`](execution_plan.md) §2 W-A6 · authority: `remediation_plan.md` §4 R-07 / D-08 / D-1.12 (ADR-026).*

## 1. Result summary

| Check | Result |
| --- | --- |
| Canonical features / rows | 94 / 6,819 |
| Columns with raw max ≥ 1e6 | **24** |
| Non-finite post-transform values (24 cols) | **0** |
| Post-transform bulk-IQR collapse (< 1e-6) | **0** |
| Rank order preserved (Spearman pre↔post) | 22/24 = 1.0; 2/24 = 0.999998 |
| Lowest post bulk-IQR | 1.77e-4 (`Current Asset Turnover Rate`) |
| Fitted λ range | −68.19 (`Current Ratio`) to +0.305 (`Total Asset Growth Rate`) |
| Spearman |ρ| ≥ 0.95 pairs / clusters | **49 pairs / 16 clusters** (largest = 6) |
| Exact algebraic identities (|ρ| = 1.0) | 5 pairs |

**No data-integrity failure**: every flagged column transforms to finite values and preserves rank order, and no column's bulk collapses below the 1e-6 falsification threshold. The audit does **not** support removing or winsorizing any column; it also does **not** support the current ADR-026 claim that the extreme values are uniformly "genuine distress signals" (§4). The correct rationale is **no removal without provenance** (§5).

## 2. Method

- Raw `data/raw/data.csv` (6,819 rows) restricted to `CANONICAL_FEATURES` (94 after ADR-024 dedup; the Phase 1 EDA's "95×95" matrix predates the dedup).
- Fitted `artifacts/preprocessor.joblib` (`YeoJohnsonTransformer`, `standardize=True`) → `pt.lambdas_`, aligned to canonical order.
- "Columns with maxima ≥ 1e6": `max(raw[col]) ≥ 1e6` over canonical features → exactly 24.
- Pre/post quantiles = min, p01, p50, p99, max, IQR (p75−p25).
- **Bulk IQR** = post-transform IQR of rows whose pre-transform value lies in the central pre-\[p01, p99\] band (the "bulk", excluding extreme tails).
- Rank preservation = Spearman between pre- and post-transform values per column.
- Spearman matrix on raw canonical features; clusters = connected components of pairs with |ρ| ≥ 0.95.
- Class-conditional tails = p50/p99 split by `Bankrupt?`.

## 3. 24-column Yeo-Johnson table

Post-transform values are standardized (zero mean, unit variance). λ is the fitted Yeo-Johnson exponent.

| # | Column | λ | Pre max | Post min | Post p01 | Post p50 | Post p99 | Post max | Post IQR | Bulk IQR | ρ | Flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Operating Expense Rate | −0.0983 | 9.99e9 | −0.7032 | −0.7032 | −0.7031 | 1.4423 | 1.4428 | 2.1234 | 2.1223 | 1.0 | ok |
| 2 | Research and development expense rate | +0.0453 | 9.98e9 | −1.1900 | −1.1900 | 0.6286 | 1.0597 | 1.0685 | 2.0946 | 2.0897 | 1.0 | ok |
| 3 | Interest-bearing debt interest rate | −1.5773 | 9.90e8 | −0.1899 | −0.1899 | −0.1871 | 5.4120 | 5.4120 | 0.00291 | 0.00283 | 1.0 | ok |
| 4 | Revenue Per Share (Yuan ¥) | −13.0486 | 3.02e9 | −1.6623 | −1.5678 | −0.1831 | 2.9267 | 3.3180 | 1.3107 | 1.2788 | 1.0 | ok |
| 5 | Total Asset Growth Rate | +0.3051 | 9.99e9 | −2.4362 | −2.4362 | 0.4250 | 0.8184 | 0.8418 | 0.3592 | 0.3403 | 1.0 | ok |
| 6 | Net Value Growth Rate | −13.9962 | 9.33e9 | −0.3695 | −0.1436 | −0.0482 | 0.4600 | 49.5001 | 0.04047 | 0.03943 | 1.0 | ok |
| 7 | Current Ratio | −68.1906 | 2.75e9 | −2.7694 | −2.0037 | −0.1579 | 2.2901 | 2.3278 | 1.3551 | 1.3269 | 1.0 | ok |
| 8 | Quick Ratio | −9.9435 | 9.23e9 | −1.0284 | −0.9854 | −0.2777 | 3.9512 | 9.5745 | 0.7233 | 0.7032 | 1.0 | ok |
| 9 | Total debt/Total net worth | −13.1839 | 9.94e9 | −1.0523 | −0.9770 | −0.2357 | 3.5771 | 10.5596 | 0.8798 | 0.8582 | 1.0 | ok |
| 10 | Accounts Receivable Turnover | −11.8508 | 9.74e9 | −0.3112 | −0.2569 | −0.1549 | 3.2204 | 13.3990 | 0.1193 | 0.1167 | 1.0 | ok |
| 11 | Average Collection Days | −10.8140 | 9.73e9 | −1.0668 | −1.0044 | −0.1029 | 1.9368 | 13.0272 | 0.6462 | 0.6310 | 1.0 | ok |
| 12 | Inventory Turnover Rate (times) | −0.0412 | 9.99e9 | −0.8671 | −0.8670 | −0.8669 | 1.2267 | 1.2282 | 2.0524 | 2.0516 | 1.0 | ok |
| 13 | Fixed Assets Turnover Frequency | −0.2429 | 9.99e9 | −0.4713 | −0.4712 | −0.4709 | 2.1300 | 2.1302 | 0.00216 | 0.001997 | 1.0 | low bulk |
| 14 | Revenue per person | −12.9823 | 8.81e9 | −1.3002 | −1.1656 | −0.3161 | 3.1291 | 3.3211 | 1.1136 | 1.0879 | 1.0 | ok |
| 15 | Allocation rate per person | −9.9523 | 9.57e9 | −0.8388 | −0.8227 | −0.3029 | 4.7650 | 6.3236 | 0.7004 | 0.6750 | 1.0 | ok |
| 16 | Quick Assets/Current Liability | −12.9818 | 8.82e9 | −1.1741 | −1.1095 | −0.2896 | 3.9861 | 7.9251 | 0.8030 | 0.7752 | 1.0 | ok |
| 17 | Cash/Current Liability | −4.1197 | 9.65e9 | −0.4830 | −0.4765 | −0.3009 | 4.5520 | 8.6417 | 0.3922 | 0.3798 | 1.0 | ok |
| 18 | Inventory/Current Liability | −2.9547 | 9.91e9 | −0.3197 | −0.3197 | −0.1653 | 7.8260 | 7.8260 | 0.1868 | 0.1822 | 0.999998 | ok |
| 19 | Long-term Liability to Current Assets | −2.6277 | 9.54e9 | −0.2585 | −0.2585 | −0.2192 | 7.3472 | 7.3472 | 0.1771 | 0.1695 | 0.999998 | ok |
| 20 | Current Asset Turnover Rate | −0.2411 | 1.00e10 | −0.4700 | −0.4700 | −0.4699 | 2.1310 | 2.1310 | 0.000193 | 0.000177 | 1.0 | low bulk |
| 21 | Quick Asset Turnover Rate | −0.0842 | 1.00e10 | −0.7370 | −0.7369 | −0.7369 | 1.3790 | 1.3795 | 2.0944 | 2.0932 | 1.0 | ok |
| 22 | Cash Turnover Rate | +0.0640 | 1.00e10 | −1.2735 | −1.2735 | 0.6110 | 0.9959 | 1.0032 | 2.1300 | 2.1263 | 1.0 | ok |
| 23 | Fixed Assets to Assets | −2.0467 | 8.32e9 | −1.6689 | −1.6292 | −0.0703 | 1.9493 | 3.5253 | 1.6744 | 1.6333 | 1.0 | ok |
| 24 | Total assets to GNP price | −7.8723 | 9.82e9 | −0.4302 | −0.4186 | −0.2925 | 5.5184 | 8.0365 | 0.2832 | 0.2763 | 1.0 | ok |

**Falsification verdict:** no non-finite post values; no bulk IQR < 1e-6; rank order preserved (the two 0.999998 values are float-tie effects from clipping/standardization, not reordering). Two columns have a **low-information bulk** (`Current Asset Turnover Rate` 1.77e-4, `Fixed Assets Turnover Frequency` 2.0e-3): the extreme tail dominates, compressing the central body to near-constant. This is a data-quality observation, not a gate failure; retain under the provenance rule until provenance is established.

## 4. Spearman clusters (|ρ| ≥ 0.95)

49 pairs form 16 clusters. Several are **exact algebraic identities** (|ρ| = 1.0), i.e. the same information under different names — provenance is arithmetic, not empirical:

| Cluster (size) | Members (abbreviated) |
| --- | --- |
| 6 | ROA(A) · Persistent EPS · Per-share PBT · PBT/Paid-in capital · Net Income/Total Assets · Net Income/Equity |
| 5 | Total debt/Net worth · Debt ratio % · Net worth/Assets · Liability to Equity · Equity to Liability |
| 4 | Cash Flow to Sales · Cash Flow/Total Assets · Cash Flow/Liability · Cash Flow/Equity |
| 3 | Operating Gross Margin · Realized Sales Gross Margin · Gross Profit to Sales |
| 3 | Pre-tax net Interest Rate · After-tax net Interest Rate · Continuous interest rate |
| 3 | Net Value Per Share (A/B/C) |
| 3 | Current Liability to Assets · Current Liabilities/Equity · Current Liability to Equity |
| 2 | ROA(C) · ROA(B) |
| 2 | Cash flow rate · Operating Funds to Liability |
| 2 | Cash Flow Per Share · CFO to Assets |
| 2 | Operating Profit Per Share · Operating profit/Paid-in capital |
| 2 | After-tax Net Profit Growth Rate · Regular Net Profit Growth Rate |
| 2 | Current Ratio · Current Liability to Current Assets (ρ = −0.9991) |
| 2 | Quick Ratio · Quick Assets/Current Liability |
| 2 | Long-term fund suitability (A) · Fixed Assets to Assets (ρ = −0.953) |
| 2 | Accounts Receivable Turnover · Average Collection Days (ρ = −0.9589) |

Exact identities (|ρ| = 1.0): `Operating Gross Margin` ↔ `Gross Profit to Sales`; `Debt ratio %` ↔ `Net worth/Assets` (−1.0); `Debt ratio %` ↔ `Equity to Liability` (−1.0); `Net worth/Assets` ↔ `Equity to Liability` (+1.0); `Current Liabilities/Equity` ↔ `Current Liability to Equity` (+1.0). These are algebraically redundant and are the strongest candidates for *future* consolidation — but only with documented provenance, not removal by correlation alone.

## 5. Class-conditional tails (p99 and p50 by class)

| Column | p99 healthy | p99 bankrupt | p50 healthy | p50 bankrupt | Pattern |
| --- | --- | --- | --- | --- | --- |
| Operating Expense Rate | 9.79e9 | 9.76e9 | 0.0003 | 0.0003 | extreme in both |
| R&D expense rate | 9.44e9 | 9.35e9 | 5.43e8 | 1.55e8 | extreme in both |
| Interest-bearing debt interest rate | 7.60e8 | 0.0011 | 0.0003 | 0.0005 | healthy-only tail |
| Revenue Per Share | 0.2153 | 0.1552 | 0.0276 | 0.0189 | healthy higher |
| Total Asset Growth Rate | 9.76e9 | 8.93e9 | 6.44e9 | 5.42e9 | extreme in both |
| Net Value Growth Rate | 0.0012 | 0.0007 | 0.0005 | 0.0004 | healthy higher |
| Current Ratio | 0.0747 | 0.0242 | 0.0108 | 0.0060 | healthy higher |
| Quick Ratio | 0.0657 | 0.0629 | 0.0076 | 0.0028 | healthy higher |
| Total debt/Total net worth | 0.0328 | 0.6222 | 0.0054 | 0.0157 | bankrupt tail ↑ |
| Accounts Receivable Turnover | 0.0252 | 0.0530 | 0.0010 | 0.0009 | bankrupt tail ↑ |
| Average Collection Days | 0.0212 | 0.0386 | 0.0066 | 0.0068 | bankrupt tail ↑ |
| Inventory Turnover Rate | 9.73e9 | 9.81e9 | 0.0007 | 5.16e7 | extreme in both |
| Fixed Assets Turnover Frequency | 9.46e9 | 9.79e9 | 0.0006 | 0.0012 | extreme in both |
| Revenue per person | 0.2685 | 0.2732 | 0.0185 | 0.0203 | similar |
| Allocation rate per person | 0.1558 | 0.3436 | 0.0077 | 0.0143 | bankrupt tail ↑ |
| Quick Assets/Current Liability | 0.0667 | 0.0237 | 0.0081 | 0.0035 | healthy higher |
| Cash/Current Liability | 0.1714 | 6.82e9 | 0.0051 | 0.0013 | bankrupt-only tail |
| Inventory/Current Liability | 1.43e9 | 5.22e8 | 0.0066 | 0.0044 | extreme in both |
| Long-term Liability to Current Assets | 1.40e9 | 0.8557 | 0.0019 | 0.0064 | healthy-only tail |
| Current Asset Turnover Rate | 9.79e9 | 9.74e9 | 0.0002 | 0.0003 | extreme in both |
| Quick Asset Turnover Rate | 9.84e9 | 9.63e9 | 0.0002 | 0.0004 | extreme in both |
| Cash Turnover Rate | 9.63e9 | 9.38e9 | 1.06e9 | 1.31e9 | extreme in both |
| Fixed Assets to Assets | 0.7834 | 0.8770 | 0.1946 | 0.2900 | bankrupt higher |
| Total assets to GNP price | 0.1570 | 2.20e9 | 0.0021 | 0.0039 | bankrupt-only tail |

**Key finding:** extreme values are **not uniformly distress-specific**. Many of the largest tails appear at similar magnitude in both classes (e.g. `Operating Expense Rate`, `Total Asset Growth Rate`, `Inventory Turnover Rate`, `Current/Quick Asset Turnover Rate`, `Cash Turnover Rate`), while a few are class-divergent (`Cash/Current Liability`, `Total assets to GNP price`, `Interest-bearing debt interest rate`, `Total debt/Total net worth`). This contradicts a blanket "extreme = genuine distressed risk signal" rationale.

## 6. D-1.12 rationale restatement

**Current ADR-026 rationale** asserts the extremes are "genuine distressed SME risk signals rather than data measurement corruption," and that retention "preserves the tail-risk signal." The class-conditional evidence above does not support that blanket claim.

**Restated rationale (proposed):** *No removal without provenance.* Extreme values are retained because their provenance (source magnitude/units, measurement validity) has not been established — not because they are asserted to be uniformly distress-specific. Removing or winsorizing them would also require provenance (evidence of measurement error). The transform (Yeo-Johnson) manages the skew without deleting rows; the audit shows this preserves rank order and keeps the bulk finite for all 24 flagged columns. Any future feature consolidation (especially the 5 algebraic-identity pairs) requires documented provenance and a change-managed decision, not correlation alone.

**Proposed ADR-026 body change-note (change-management, not applied):** replace the sentence "Extreme financial ratios ... represent genuine distressed SME risk signals rather than data measurement corruption" with the provenance-neutral restatement above; and replace the downstream clause "Tier 2 Monte Carlo P90 loss distribution and Tier 3 CRO persona tail-loss interpretation" with the W-A2-corrected phrasing ("Tier 2 P10/P50/P90 default-probability bands; Tier 3 `p90_pd` scenario-conditional PD"). This aligns ADR-026 with the W-A2 change-note.

## 7. Open items / follow-ups (not W-A6 scope)

1. Two columns have a low-information bulk (`Current Asset Turnover Rate`, `Fixed Assets Turnover Frequency`). Retain under the provenance rule; if provenance later shows scaling error, revisit. Not a Wave A change.
2. Five exact algebraic-identity pairs are redundant-by-arithmetic. Consolidation is a separate, owner-approved feature-contract change (R-01/D-08), not a correlation-driven removal.
3. The class-conditional tail mix should inform the R-01 seed-case labels (some extremes are healthy-class too); it does not justify changing the current no-removal policy.
