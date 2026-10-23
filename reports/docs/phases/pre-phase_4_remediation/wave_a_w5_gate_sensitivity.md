# Wave A · W-A5 Evidence Report — Tier 1 Gate Sensitivity & Selection-Leakage Audit

*ACRAS · 2026-10-23 · Wave A (measure-only; no retrain, no gate change).*
*Source: [`execution_plan.md`](execution_plan.md) §2 W-A5 · authority: `remediation_plan.md` §4 R-06 / D-07 / INV-3 (ADR-003).*

## 1. Result summary

| Quantity | Value |
| --- | --- |
| Test set (promoted model) | n = 1364 · base rate 3.47% |
| Baseline Brier / AUC / ECE | 0.020766 / 0.959496 / 0.007107 |
| δ\* (uniform logit-shift up) | **1.3804** |
| δ\* mean-PD shift | **+0.0410** (3.47% → 7.57%) |
| γ\* (underconfident logit-scale) | **0.4043** |
| γ\* mean-PD shift | +0.0665 |
| ΔAUC at δ\* and γ\* | 0.000000 (rank-invariant) |
| Winner CV Brier (out-of-fold) | 0.022884 (vs test 0.020766) |
| CV-vs-test Spearman rank corr. | 0.783 |
| Test-winner selection optimism | −0.002118 Brier |

The INV-3 Brier gate is **robust**: it tolerates a +1.38 uniform logit-shift (raising the base rate ~2.2×) before tripping, with ROC-AUC held exactly constant. Selection leakage on the test set is real but modest: the promoted model's true (CV) Brier is ~0.0229, still comfortably below the 0.030 gate. **No retrain is implied** (D-07 stop rule not triggered).

## 2. Method

- Promoted bundle `artifacts/promoted_model_bundle.joblib` (XGBoost, unweighted, isotonic) loaded via `load_promoted_bundle`; test probabilities from `model.predict_proba(X_test)` on the persisted `data/processed` partitions.
- Distortion functions are pure and unit-tested in `src/pipelines/training/gate_sensitivity.py` (`logit_shift`, `logit_scale`, `expected_calibration_error`, `find_logit_shift_trip`, `find_logit_scale_trip`, `sweep_logit_shift`). Logits are clipped to ±38 before the sigmoid (W-A5 falsification).
- δ\* and γ\* found by bisection to the first distortion where Brier exceeds 0.030.
- CV-vs-test ranking: for each of the 12 candidates, out-of-fold (5-fold) calibrated predictions on the **train** split (`cross_val_predict` over the `CalibratedClassifierCV(cv=5)` pipeline) give CV Brier; test Brier from the held-out split.

## 3. Distortion-trip results (Part A)

| Distortion | Trip value | Brier at trip | Mean-PD shift | ECE at trip | AUC at trip |
| --- | --- | --- | --- | --- | --- |
| δ (logit-shift up) | 1.3804 | 0.030 | +0.0410 | 0.0435 | 0.959496 |
| γ (logit-scale, underconfident) | 0.4043 | 0.030 | +0.0665 | 0.0716 | 0.959496 |

- The overconfident direction (γ > 1) does **not** trip the gate for this low-base-rate model (it pushes the negative majority toward zero and lowers Brier); the gate-relevant scale failure is **underconfidence** (γ < 1), which inflates predictions for the negative majority.
- ECE at the trip points (0.043/0.072) exceeds the gate Brier's own ECE baseline (0.007), confirming the gate would catch the induced miscalibration if ECE were a separate check.
- **Caveat (falsification):** δ\*/γ\* are measured on the selection test set, so the headroom (0.030 − 0.0208 = 0.0092) is **optimistic**. The CV-based headroom is 0.030 − 0.0229 = 0.0071.

## 4. Selection-leakage / CV-vs-test ranking (Part B)

Test-set ranking (Brier asc, AUC tiebreak) vs out-of-fold CV ranking across the 12 candidates:

| Test rank | Model | Test Brier | CV Brier | CV rank | Δ rank |
| --- | --- | --- | --- | --- | --- |
| 1 | xgboost / unweighted / isotonic **(promoted)** | 0.020766 | 0.022884 | 3 | −2 |
| 2 | xgboost / unweighted / sigmoid | 0.021031 | 0.024110 | 8 | −6 |
| 3 | lightgbm / unweighted / sigmoid | 0.021046 | 0.022714 | 1 | +2 |
| 4 | lightgbm / unweighted / isotonic | 0.021302 | 0.022763 | 2 | +2 |
| 5 | xgboost / weighted / isotonic | 0.021416 | 0.023777 | 6 | −1 |
| 6 | lightgbm / weighted / isotonic | 0.021718 | 0.023543 | 5 | +1 |
| 7 | lightgbm / weighted / sigmoid | 0.021807 | 0.023515 | 4 | +3 |
| 8 | xgboost / weighted / sigmoid | 0.022281 | 0.023954 | 7 | +1 |
| 9 | logistic / unweighted / isotonic | 0.024298 | 0.024794 | 10 | −1 |
| 10 | logistic / weighted / isotonic | 0.024624 | 0.024720 | 9 | +1 |
| 11 | logistic / unweighted / sigmoid | 0.024997 | 0.025111 | 11 | 0 |
| 12 | logistic / weighted / sigmoid | 0.025941 | 0.026456 | 12 | 0 |

- The **promoted model is test-rank 1 but CV-rank 3**; its test Brier (0.020766) understates its CV Brier (0.022884) by 0.002118 — the selection effect from ranking 12 candidates on the same held-out set.
- `xgboost / unweighted / sigmoid` is the most over-ranked by test selection (test 2 → CV 8).
- Spearman rank correlation 0.783: the test ranking is directionally informative but not a reliable independent estimate.
- The top candidates are tightly clustered in CV Brier (0.0227–0.0230), so the "winner" is not meaningfully distinguished from the next two tree candidates under CV.

## 5. Falsification checks

- Unit tests (`tests/unit/test_gate_sensitivity.py`) assert: |ΔAUC| ≤ 1e-12 across a strictly increasing δ sweep while Brier monotonically degrades above 0.030; δ=0 reproduces the baseline Brier; extremes are clipped to ±38 with no non-finite values; γ\*=underconfidence trip.
- On the real promoted model, ΔAUC at both δ\* and γ\* is 0.000000 (0.959496 constant), confirming rank-invariance.
- δ=0 reproduces the ADR-027 test Brier (0.020766) exactly (identity short-circuit).

## 6. D-07 recommendation (retain vs retrain)

**Retain the frozen promoted model.** The selection optimism is quantified (0.0021 Brier) and does not change the gate verdict: the promoted model's CV Brier (0.0229) remains below 0.030, and its AUC (0.959) is unaffected by the monotone distortions. Retraining would only be warranted if an owner-approved target required an *independent* final estimate tighter than the current CV margin — which is not the case under the approved D-07 direction ("quantify first; do not retrain"). Options, if the owner later wants a cleaner final metric: (a) accept the current CV Brier 0.0229 as the disclosed conservative estimate, or (b) re-rank on a nested/repeated-CV protocol before any future freeze. Neither is required now.

## 7. Code deliverable

- `src/pipelines/training/gate_sensitivity.py` (new): pure distortion + trip + ECE functions.
- `tests/unit/test_gate_sensitivity.py` (new): 7 tests covering the W-A5 falsification.

## 8. Open items

1. δ\*/γ\* are test-set (optimistic) estimates; a CV-anchored re-derivation would shrink the headroom but is not needed for the D-07 decision.
2. The gate has no ECE check (Brier only). The trip-point ECE (0.043–0.072) shows ECE would add a second, earlier-triggering signal; adding an ECE/calibration-curve check to INV-3 is a candidate for a future owner decision, not part of W-A5.
