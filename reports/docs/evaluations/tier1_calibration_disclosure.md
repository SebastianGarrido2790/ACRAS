# Tier 1 Calibration Disclosure (A-04 / W-A5 / D-07)

*Status: recorded; freeze/retrain decision not yet made (A-04 approved as retain with disclosure).*

## Evidence (from W-A5 / `wave_a_return.md` / ADR-027 / promotion gate)

- Frozen Tier 1 model: unweighted XGBoost, isotonic calibration (`ADR-027`).
- Test-set metrics (not independent — selection-leakage optimistic): Brier `0.020766`, AUC `0.959496`, KS `0.793182`.
- 5-fold CV calibration (independent of selection): Brier `0.022884`. **This is the conservative (disclosed) estimate.**
- Mean predicted PD (post-calibration on full data): `3.47%`; observed base rate (44 / 1,364): `3.2258%`.
- Gate threshold `brier_threshold: 0.030`; CV Brier `0.022884` is below threshold; selection-effect optimism quantified (`wave_a_return.md` W-A5).
- Selection-leakage effect (test-set used for ranking 12 candidates): documented as optimistic; independent final evaluation not performed.
- Retrain: **not authorized** until selection-effect quantified and owner records freeze/retrain decision (`remediation_plan.md` §4 R-06 / A-04).

## Disclosure statement (for human review / audit)

The frozen Tier 1 artifact (promoted `794d6bc`, ADR-027) carries the disclosed CV Brier `0.022884` (5-fold CV, isotonic). Test-set Brier `0.020766` is the optimistic ranking metric due to selection-leakage; it is not presented as an independent final estimate. No calibration change, feature-handling change, or promotion-gate change is made by this disclosure.

## Open conditions

- Owner must record freeze vs. retrain (`remediation_plan.md` §9.3 / A-04 condition).
- If retrain authorized: reserve independent test set (not used in selection); compare Platt vs. isotonic inside selection; add reliability-curve criterion if evidence supports.
