# Wave A · W-A6 Evidence Report — Feature Quality & Yeo-Johnson λ / Range Audit

*ACRAS · 2026-10-23 · Wave A (measure-only; no retrain, no removal, no gate change).*
*Source: [`execution_plan.md`](execution_plan.md) §2 W-A6 · authority: `remediation_plan.md` §4 R-07 / D-1.12 / ADR-025 / ADR-026.*

## 1. Result summary

| Check | Result |
| --- | --- |
| Feature columns (canonical) | 94 |
| Columns with max ≥ 10⁶ | **24** |
| Post-transform collapse (norm IQR < 10⁻⁶) | **0 of 24** |
| Non-finite post-transform values | **0** |
| Pre↔post rank preservation (min Spearman) | **0.99999784** |
| Spearman pairs \|ρ\| ≥ 0.95 (95×95) | **49** |
| Smallest post-transform bulk IQR (normalized) | **7.43×10⁻⁵** (Current Asset Turnover Rate) |

**Falsification passes:** Yeo-Johnson preserves rank order on all 24 extreme columns, produces no non-finite values, and never collapses the [0,1] bulk below 10⁻⁶. **No retrain is forced by this audit** (W-A6 stop rule not triggered).

The audit does reveal that the ≥10⁶ magnitudes are **sentinel-like encoding artifacts, not tail risk**, and that YJ is fitting very negative λ (−68 to −2) to them. That is recorded as an option for future provenance work, not an authorized change.

## 2. Fitted Yeo-Johnson λ (24 columns, |max| ≥ 10⁶)

Sentinel fraction = share of rows with \|value\| ≥ 10⁶; `c0` = non-bankrupt, `c1` = bankrupt.

| Column | λ | ≥10⁶ frac | c0 frac | c1 frac |
| --- | ---: | ---: | ---: | ---: |
| Operating Expense Rate | −0.0983 | 33.4% | 33.5% | 30.5% |
| Research and development expense rate | 0.0453 | 59.1% | 59.3% | 54.6% |
| Interest-bearing debt interest rate | −1.5773 | 3.2% | 3.3% | 0.9% |
| Revenue Per Share (Yuan ¥) | −13.05 | 0.07% | 0.08% | 0.00% |
| Total Asset Growth Rate | 0.3051 | **88.2%** | 88.0% | **96.4%** |
| Net Value Growth Rate | −13.99 | 0.03% | 0.02% | 0.45% |
| Current Ratio | **−68.19** | 0.01% | 0.02% | 0.00% |
| Quick Ratio | −9.943 | 0.13% | 0.12% | 0.45% |
| Total debt/Total net worth | −13.18 | 0.12% | 0.11% | 0.45% |
| Accounts Receivable Turnover | −11.85 | 0.32% | 0.32% | 0.45% |
| Average Collection Days | −10.81 | 0.26% | 0.26% | 0.45% |
| Inventory Turnover Rate (times) | −0.0412 | 43.2% | 42.9% | 53.6% |
| Fixed Assets Turnover Frequency | −0.2429 | 18.0% | 17.3% | **38.2%** |
| Revenue per person | −12.98 | 0.03% | 0.02% | 0.45% |
| Allocation rate per person | −9.952 | 0.18% | 0.17% | 0.45% |
| Quick Assets/Current Liability | −12.98 | 0.04% | 0.05% | 0.00% |
| Cash/Current Liability | −4.120 | 0.67% | 0.47% | **6.82%** |
| Inventory/Current Liability | −2.955 | 1.45% | 1.45% | 1.36% |
| Long-term Liability to Current Assets | −2.628 | 1.60% | 1.62% | 0.91% |
| Current Asset Turnover Rate | −0.2411 | 18.1% | 17.9% | 24.1% |
| Quick Asset Turnover Rate | −0.0842 | 34.9% | 34.6% | 44.1% |
| Cash Turnover Rate | 0.0640 | **62.1%** | 61.4% | **83.6%** |
| Fixed Assets to Assets | −2.047 | 0.01% | 0.00% | 0.45% |
| Total assets to GNP price | −7.872 | 0.29% | 0.26% | 1.36% |

The pattern is bimodal: the same column has a central bulk at ~10⁻⁴ and a large discrete mass at 10⁶–10¹⁰ (e.g. Total Asset Growth Rate: 88% of rows ≥10⁶, median of the remaining ~10⁻⁴). These are magnitude-class artifacts (lost decimals / sentinel encodings), consistent with the remediation plan's observation that 10⁹–10¹⁰ ratio magnitudes "look like encoding artifacts rather than tail risk."

## 3. Post-transform quantile ranges (standardized output)

`normIQR` = IQR after min–max scaling to [0,1] over the column (the "[0,1] bulk IQR" falsification metric).

| Column | min | p01 | p50 | p99 | max | IQR | normIQR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Operating Expense Rate | −0.703 | −0.703 | −0.703 | 1.44 | 1.44 | 2.12 | 0.989 |
| Research and development expense rate | −1.19 | −1.19 | 0.629 | 1.06 | 1.07 | 2.09 | 0.927 |
| Interest-bearing debt interest rate | −0.190 | −0.190 | −0.187 | 5.41 | 5.41 | 2.91e−3 | 5.19e−4 |
| Revenue Per Share | −1.66 | −1.57 | −0.183 | 2.93 | 3.32 | 1.31 | 0.263 |
| Total Asset Growth Rate | −2.44 | −2.44 | 0.425 | 0.818 | 0.842 | 0.359 | 0.110 |
| Net Value Growth Rate | −0.369 | −0.144 | −0.048 | 0.460 | 49.5 | 0.0405 | 8.12e−4 |
| Current Ratio | −2.77 | −2.00 | −0.158 | 2.29 | 2.33 | 1.36 | 0.266 |
| Quick Ratio | −1.03 | −0.985 | −0.278 | 3.95 | 9.57 | 0.723 | 0.068 |
| Total debt/Total net worth | −1.05 | −0.977 | −0.236 | 3.58 | 10.6 | 0.880 | 0.0758 |
| Accounts Receivable Turnover | −0.311 | −0.257 | −0.155 | 3.22 | 13.4 | 0.119 | 8.70e−3 |
| Average Collection Days | −1.07 | −1.00 | −0.103 | 1.94 | 13.0 | 0.646 | 0.0459 |
| Inventory Turnover Rate | −0.867 | −0.867 | −0.867 | 1.23 | 1.23 | 2.05 | 0.980 |
| Fixed Assets Turnover Frequency | −0.471 | −0.471 | −0.471 | 2.13 | 2.13 | 2.16e−3 | 8.32e−4 |
| Revenue per person | −1.30 | −1.17 | −0.316 | 3.13 | 3.32 | 1.11 | 0.241 |
| Allocation rate per person | −0.839 | −0.823 | −0.303 | 4.77 | 6.32 | 0.700 | 0.0978 |
| Quick Assets/Current Liability | −1.17 | −1.11 | −0.290 | 3.99 | 7.93 | 0.803 | 0.0882 |
| Cash/Current Liability | −0.483 | −0.476 | −0.301 | 4.55 | 8.64 | 0.392 | 0.0430 |
| Inventory/Current Liability | −0.320 | −0.320 | −0.165 | 7.83 | 7.83 | 0.187 | 0.0229 |
| Long-term Liability to Current Assets | −0.259 | −0.259 | −0.219 | 7.35 | 7.35 | 0.177 | 0.0233 |
| Current Asset Turnover Rate | −0.470 | −0.470 | −0.470 | 2.13 | 2.13 | 1.93e−4 | 7.43e−5 |
| Quick Asset Turnover Rate | −0.737 | −0.737 | −0.737 | 1.38 | 1.38 | 2.09 | 0.990 |
| Cash Turnover Rate | −1.27 | −1.27 | 0.611 | 0.996 | 1.00 | 2.13 | 0.936 |
| Fixed Assets to Assets | −1.67 | −1.63 | −0.070 | 1.95 | 3.53 | 1.67 | 0.322 |
| Total assets to GNP price | −0.430 | −0.419 | −0.293 | 5.52 | 8.04 | 0.283 | 0.0334 |

No column has `normIQR` < 10⁻⁶ (minimum 7.43×10⁻⁵) and no non-finite values appear. The smallest bulks are still resolved by the transform, so the falsification does not fire.

## 4. Spearman clusters (95×95: 94 features + target)

49 feature pairs have \|ρ\| ≥ 0.95 (connected components → clusters). These are logical/accounting-identity relations, distinct from the single exact duplicate removed by D-1.10.

| Size | Members |
| ---: | --- |
| 6 | Net Income to Stockholder's Equity · Net Income to Total Assets · Net profit before tax/Paid-in capital · Per Share Net profit before tax · Persistent EPS · ROA(A) |
| 5 | Debt ratio % · Equity to Liability · Liability to Equity · Net worth/Assets · Total debt/Total net worth |
| 4 | Cash Flow to Equity · Cash Flow to Liability · Cash Flow to Sales · Cash Flow to Total Assets |
| 3 | Gross Profit to Sales · Operating Gross Margin · Realized Sales Gross Margin |
| 3 | After-tax net Interest Rate · Continuous interest rate (after tax) · Pre-tax net Interest Rate |
| 3 | Net Value Per Share (A) · (B) · (C) |
| 3 | Current Liabilities/Equity · Current Liability to Assets · Current Liability to Equity |
| 2 | ROA(B) · ROA(C) |
| 2 | Cash flow rate · Operating Funds to Liability |
| 2 | CFO to Assets · Cash Flow Per Share |
| 2 | Operating Profit Per Share · Operating profit/Paid-in capital |
| 2 | After-tax Net Profit Growth Rate · Regular Net Profit Growth Rate |
| 2 | Current Liability to Current Assets · Current Ratio |
| 2 | Quick Assets/Current Liability · Quick Ratio |
| 2 | Fixed Assets to Assets · Long-term fund suitability ratio (A) |
| 2 | Accounts Receivable Turnover · Average Collection Days |

Not acted on: W-A6 is characterization; cluster-based collapse is not authorized. Note for future work: `Current Ratio`/`Current Liability to Current Assets` and `Quick Ratio`/`Quick Assets/Current Liability` are near-reciprocal identities.

## 5. Class-conditional tails

The artifact mass is **class-correlated** in several columns — bankrupt (`c1`) rows carry the 10⁶–10¹⁰ magnitude far more often:

| Column | c0 ≥10⁶ | c1 ≥10⁶ | Direction |
| --- | ---: | ---: | --- |
| Cash/Current Liability | 0.47% | **6.82%** | ↑ in bankruptcy |
| Total Asset Growth Rate | 88.0% | **96.4%** | ↑ |
| Cash Turnover Rate | 61.4% | **83.6%** | ↑ |
| Fixed Assets Turnover Frequency | 17.3% | **38.2%** | ↑ |
| Current Asset Turnover Rate | 17.9% | 24.1% | ↑ |
| Research and development expense rate | 59.3% | 54.6% | ↓ |

Because the artifact correlates with the label, it is not provably pure noise. Provenance is required before any removal: the huge values may be genuine ratios from near-zero denominators (which carry distress signal) **or** parsing artifacts that leak label-correlated noise. This is the exact ambiguity the restated rationale addresses.

## 6. D-1.12 rationale correction

**Current ADR-026 wording (to be corrected):** extremes "represent genuine distressed SME risk signals rather than data measurement corruption."

**Restated rationale (adopt):** *"No removal without provenance."* We retain all rows because (a) removal/winsorization requires evidence that a value is not a genuine measurement, and (b) the audit shows many 10⁹–10¹⁰ magnitudes are sentinel-like encoding artifacts whose provenance is unverified — so neither "these are tail risk" nor "these are corruption" is established. Retaining is the conservative choice pending a provenance audit; the decision to *not remove* does not assert the tails are risk signal.

Follow-up (not part of W-A6, requires owner decision): a provenance audit of the 24 columns to distinguish encoding artifacts from genuine near-zero-denominator ratios before any future feature change.

## 7. Falsification & conclusion

- Rank order preserved (min Spearman 0.99999784); no collapse (min normIQR 7.43×10⁻⁵); no non-finite values → **pass**.
- YJ `standardize=True` output keeps informative bulk IQR despite extreme λ; fitted λ on the artifact columns (−68 to −2) is noted as fragile but does not fail the check.
- **No retrain forced.** Options recorded (provenance audit; artifact-aware λ) are not authorized by measurement.

## 8. Open items

1. No code/test change is required by W-A6 (characterization only); no new test was added.
2. ADR-026 rationale correction and the provenance-audit follow-up need owner/change-management sign-off before any doc edit.
3. `Current Ratio` λ = −68.19 is the most extreme; it is driven by a 0.01% artifact mass and is the strongest candidate for the provenance audit.
