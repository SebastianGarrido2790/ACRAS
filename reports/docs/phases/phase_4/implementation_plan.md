# Phase 4 Planning / Approval — Pre-Phase-4 Remediation Exit

*Status: DRAFT — awaits separate owner approval (Gate R-A item 4, `remediation_plan.md` §6 / §9.1). Not applied or implemented; this file records the scope ready for approval, not authorization.*

*Evidence base: Wave A return (`wave_a_return.md`), Wave B schema (`evidence_bundle.py` v2), Wave C fixtures (`sc_01`–`sc_04`) + harness (`test_offline_harness.py`), Tier 3 contracts (`tier3_contracts.md`), approved decisions A-01–A-07 (`remediation_plan.md` §9.3), A-06 applied (`794d6bc`, `c1e9c6a`).*

---

## 1. Approved Phase 4 scope (derived from `remediation_plan.md` §5 candidates + A-01/A-05 + A-06)

| Candidate | In scope? | Source / dependency | Evidence satisfied? |
|---|---|---|---|
| `p4-evidence-contract` (v2 `EvidenceBundle`) | **Yes** — core | A-01 (A+C contract) / A-05 (seed case contract) / `evidence_bundle_v2_contract.md` | v2 schema (`evidence_bundle.py`), guard (`ratios.py`), 4 fixtures + harness |
| `p4-persona-interpretation` (CRO / Growth / Capital) | **Yes — mechanism only** | PRD FR6 / `tier3_persona_architecture.md` §3 / D-02 / D-03 / `tier3_contracts.md` | Verdict schema locked (`approve`/`conditional`/`reject`); rubrics reworded (`p90_pd`, `concentration_flag`); divergence mechanism documented; weights/threshold deferred |
| `p4-convergence-escalation` (divergence + escalation) | **Yes — structure, not calibrated values** | PRD FR7/FR8 / INV-4 / INV-9 / INV-10 / D-03 / D-06 / `tier3_contracts.md` | Divergence computed deterministically over structured fields; truth table written; HITL routing for incomplete/invalid; no LLM judge |
| `p4-report-orchestration` (report assembly) | **Yes — bounded** | PRD FR9 / INV-2 / INV-6 / INV-10 / D-05 / D-06 | Gateway contract (Phase 3); numeric grounding against bundle fields; failure/repair contract; partial persona failure surfaces HITL |

**Excluded from this scope (not prerequisites for Phase 4 planning):**
- Tier 1 retrain (`remediation_plan.md` §4 R-06 / A-04) — deferred until selection-effect evidence and owner freeze/retrain decision; current frozen artifact (`794d6bc`) disclosed.
- Dashboard framework (Phase 6) — deferred.
- Divergence weight/threshold calibration — deferred to Phase 5 (`tier3_contracts.md` §1, `remediation_plan.md` §4 R-03).
- Qualitative LLM-judge grounding (`tier3_contracts.md` §3) — deferred to D-06 evidence-first.
- Broad feature-policy change / ADR-026 supersession — preserved unless audit evidence establishes (`tier3_contracts.md` §4).

---

## 2. Gate R-A exit evidence (verified before Phase 4 planning)

| Gate item | Evidence | Status |
|---|---|---|
| R-A 1 — FR3 / `p90_pd` / loss-field resolution | A-06 (`794d6bc`); `p90_pd` computed (`evidence_bundle.py`); excluded fields (`tail_loss_estimate`, `capital_consumption_estimate`) documented (`evidence_bundle_v2_contract.md` §2) | Closed |
| R-A 2 — Tier 3 contracts / D-02 / divergence | `tier3_contracts.md` (contracts + deferred mechanism); architecture docs reflect `approve`/`conditional`/`reject` canonical; divergence over structured fields; no duplicate analyst nodes described | Resolved (mechanism); deferred (calibration) |
| R-A 3 — Seed set / fixtures / harness | `tests/fixtures/sc_01_bundle.json` (converge) / `sc_02_bundle.json` (Growth-v-Risk diverge) / `sc_03_bundle.json` (Capital-v-Risk diverge) / `sc_04_bundle.json` (incomplete/HITL); `test_offline_harness.py` (6 pass); fixtures load through `enforce_v2_contract`; ratios match `compute_financial_ratios(accounting_profile)` | Closed |
| R-A 4 — Phase 4 planning / scope / exit criteria | This document (`reports/docs/phases/phase_4/implementation_plan.md`); scope derived from approved candidates (§1); exit criteria aligned with `remediation_plan.md` §5 (falsifiable 3–5 smoke set + divergence/false-escalation reporting, no statistical claim) | Pending owner approval |

---

## 3. Gate R-B prerequisites (not blocking decoupled Tier 3 build; required for end-to-end raw-row demo / model governance)

| Gate R-B item | Dependency / evidence needed | Status / deferral |
|---|---|---|
| Dataset → ratio correction / `accounting_profile` contract (A-01 / A-05) | v2 schema + fixtures already enforce; raw-row → zero-ratio path blocked by guard (`ratios.py`); `test_tier2_sensitivity.py` flipped | Closed (contract + fixtures); service backward-compat preserved for v0/v1 |
| Tier 1 freeze/retrain (A-04) | CV Brier `0.022884` disclosed in `tier3_contracts.md`; retrain deferred to owner decision (`remediation_plan.md` §4 R-06 / `wave_a_return.md` A-04) | Deferred; no retrain authorized |
| Tier 2 semantics / unused shock settings (A-07 / W-A7 / D-10) | Characterization pinned (`test_tier2_sensitivity.py`); `macro_volatility` / `debt_service_shock_std` / `asset_haircut_std` dead config confirmed; param behavior documented; separate owner decision required for behavior change | Evidence complete; decision deferred |
| DVC / reproducibility (A-02 / R-14) | Not executed; no remote change approved; clean-clone exception remains documented | Deferred |
| Provider lifecycle (A-03 / A-07 / R-10) | Not executed; bounded verification deferred | Deferred |

---

## 4. Residual open work (listed, not hidden; not blocking this approval request)

- Divergence weight/threshold calibration — deferred to Phase 5 (`tier3_contracts.md` §1, `remediation_plan.md` §3 D-03).
- Tier 1 confidence proxy definition — deferred (`tier3_contracts.md` §2).
- Qualitative LLM-judge grounding mechanism — deferred to D-06 evidence-first (`tier3_contracts.md` §3).
- DVC stage design installation (`dvc.proposed.yaml`) — deferred (A-02).
- Gemini 2.5 Flash lifecycle verification (A-07) — deferred.
- PRD pricing/cost fixture update (`params.yaml`) — deferred (A-03).
- Remediation documentation hygiene (`remediation_plan.md`: 2 stale status lines; 15 broken relative links; `scoping_doc.md` staleness) — deferred (not blocking Phase 4).
- `AGENTS.md` tracking (`.gitignore` ignore rule) — owner question unanswered; deferred.

---

## 5. Approval request (separate owner act, `remediation_plan.md` §9.1 / §6)

**Requested decision:** Approve the Phase 4 scope as described (§1 — evidence-contract `v2`, persona interpretation mechanism only, convergence/escalation mechanism only, bounded report assembly; exclusions in §1). Confirm the deferred calibration/failure/grounding items (§3) and residual open work (§4) remain deferred without blocking Phase 4 build.

*Not authorized by this document: any code implementation of persona workers, divergence formula selection beyond mechanism, divergence weight/threshold adoption, report assembly, or any retrain/gate/model-provision change.*
