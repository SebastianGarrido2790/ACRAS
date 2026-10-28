# Wave A Return Package — Bounded Results, Contract Lock & Decisions (W-A1–W-A8)

*ACRAS · 2026-10-23 · Return from Wave A · no implementation authorized by this package.*
*Source: [`execution_plan.md`](execution_plan.md) §3 · authority: `remediation_plan.md` §3/§6/§9.*

## 1. Status

Wave A (`W-A1`–`W-A8`) is complete. Four of the five approval conditions are fully met; condition 4 is partially met because Gemini lifecycle/deprecation remains unverified. No retrain, feature-handling change, gate change, provider swap, DVC pipeline install, or remote change was made.

This package:

1. returns the bounded results and the Gate R-A / R-B status;
2. locks the `EvidenceBundle` v2 seed-case contract (pending owner approval);
3. presents the approved FR3 / `p90_pd` change note for change-management;
4. requests only the decisions Wave A evidence requires.

## 2. Results at a glance

| Task | Bounded result | Evidence |
| --- | --- | --- |
| **W-A1** pricing/lifecycle | Groq `openai/gpt-oss-20b` $0.075/$0.30 **correct**. Gemini `gemini-2.5-flash` configured $0.075/$0.30 is **wrong**; primary Vertex rate is **$0.30 in / $2.50 out** per 1M (≤200K ctx). Live call: Gemini 36 prompt / 4 completion / 490 total → 450 reasoning tokens counted once in `total`, excluded from `completion`; Groq 101 prompt / 92 completion (81 reasoning) / 193 total. Current cost formula (`prompt·in + completion·out`) **undercounts Gemini**. | [`wave_a_w1_pricing_lifecycle.md`](wave_a_w1_pricing_lifecycle.md) |
| **W-A2** v2 contract | Provenance taxonomy (`observed`/`derived`/`synthetic`); loss fields `tail_loss_estimate` and `capital_consumption_estimate` **excluded as a set**; CRO field is `p90_pd := pd_band.p90` (by reference, no duplicate); label is **scenario-conditional PD under assumed parameters (R-09)**; exact change note drafted. | [`evidence_bundle_v2_contract.md`](evidence_bundle_v2_contract.md) |
| **W-A3** GX test fix | `build_bankruptcy_suite` defaults to an **ephemeral** GX context; `save=True` opt-in for `--build-only`; `validate_dataset` fallback also ephemeral. Tracked suite digest unchanged; corrupted-data exit test still blocks training. | `src/pipelines/data_contracts.py`, `tests/unit/test_data_contracts.py`, `tests/integration/test_gate_adversarial.py` |
| **W-A4** structured output | 15/15 schema-valid per provider (Wilson 95% [0.796, 1.0]); `reject` enum and `lean` ±1.0 exercised; Gemini thinking / Groq reasoning tokens observed. **D-05 preferred route confirmed viable**: gateway-direct + Pydantic validation; no adapter needed. | [`wave_a_w4_structured_output.md`](wave_a_w4_structured_output.md) |
| **W-A5** gate sensitivity | Test Brier **0.020766**, AUC **0.959496**, ECE **0.007107**; δ\* = **1.3804** (mean-PD shift +0.0410), γ\* = **0.4043** (underconfidence); \|ΔAUC\| = 0; CV Brier **0.022884**, Spearman **0.783**, selection optimism **0.002118**. **Recommendation: retain, no retrain.** | [`wave_a_w5_gate_sensitivity.md`](wave_a_w5_gate_sensitivity.md) |
| **W-A6** feature quality | 24 columns with raw max ≥ 1e6; **0** non-finite post-transform; **0** bulk-IQR collapse; rank preserved; 49 Spearman pairs / 16 clusters; 5 algebraic identities. No removal or winsorization supported. D-1.12 restated as **no removal without provenance**. | [`wave_a_w6_feature_quality.md`](wave_a_w6_feature_quality.md) |
| **W-A7** ratio trace / Tier 2 | Raw benchmark row → **seven 0.0 ratios** (no exception); accounting inputs → correct ratios; dataset-feature ↔ required-input alias intersection **empty**. Unused shock keys have **exactly zero** effect; `asset_correlation` 0.05→0.30 widens P10–P90 **0.0435→0.1290**. Characterization test pins the seven zeros; guard deferred. | [`wave_a_w7_ratio_trace_sensitivity.md`](wave_a_w7_ratio_trace_sensitivity.md) |
| **W-A8** DVC lineage | Live `dvc.yaml` unchanged (`validate` → `stub_train`; no `dvc.lock`). Proposed `validate` → `train` → `evaluate_gate` draft validates with real `dvc dag`; `train` deps include raw + `params.yaml` + gate signal; failing gate exits non-zero and **writes no bundle**. Dataset SHA-256/MD5/size match ADR-011; clean-clone remote is **absent**. | [`wave_a_w8_dvc_lineage.md`](wave_a_w8_dvc_lineage.md) |

## 3. Condition compliance

| # | Condition | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Measure-only; stop rule; caps not forecasts. | **Met.** No retrain/feature/gate/provider/pipeline/remote change. W-A5 found no retrain need; W-A6 found no removal need; W-A7 guard deferred; W-A8 graph not installed. | §2; reports |
| 2 | W-A4 N=10–20/provider, 2–3 concurrent, `reject` enum, `lean` bounds, Gemini thinking / Groq reasoning. | **Met.** N=15/provider, up to 3 concurrent (≥6 s pacing), `reject` 5/15, `lean` ±1.0 observed, reasoning tokens observed. | W-A4 §2–§3 |
| 3 | W-A3 second falsification: corrupted-data exit test. | **Met.** Phase 0 adversarial exit test green; suite digest unchanged. | W-A3 tests |
| 4 | W-A1 primary sources + one real call proving reasoning counted once; no silent swap. | **Partially met.** Pricing/usage verified from Vertex + live calls; no model swap. Gemini lifecycle/deprecation remains **unverified** (primary page transport error). | W-A1 §3, §6 |
| 5 | W-A5 \|ΔAUC\| ≤ 1e-12, clip ±38, optimistic caveat; W-A7 seven-zeros characterization, no `ValueError`. | **Met.** \|ΔAUC\| = 0; logits clipped ±38; test sweep reported optimistic. W-A7 test asserts seven `0.0` and no exception. | W-A5 §5; W-A7 §5 |

## 4. Gate status

### Gate R-A — hard prerequisites before Phase 4 Tier 3 planning

- [ ] **FR3 / loss-field / `p90_pd` reconciliation.** Contract + change note delivered (W-A2); **application to PRD/architecture pending** (A-06).
- [ ] **Tier 3 contracts resolved or explicitly deferred.** Input (W-A2) and verdict (W-A4) resolved; divergence formula/threshold, escalation truth table, qualitative grounding, and fallback-near-threshold policy remain evidence-gated (D-03/D-06). D-02 doc/graph reflection not yet applied.
- [ ] **Seed-set scope + metrics approved; offline harness can exercise recorded verdicts.** Seed contract proposed in §5 (pending A-05); fixtures + harness are Wave C.
- [ ] **Required decisions recorded; owner approves Phase 4 planning.** Requested in §7.

### Gate R-B — upstream prerequisites for end-to-end raw-row demo / model-governance closure

- [ ] **Dataset→Tier 2 correction/contract.** W-A7 evidence complete; input-contract decision requested (A-01).
- [ ] **Tier 1 selection limitation disclosed; retain/retrain recorded.** W-A5 evidence complete; retain record requested (A-04).
- [ ] **Tier 2 output meaning + unused simulation settings documented/addressed.** Documented (W-A2/W-A7); config change deferred (R-09).
- [ ] **DVC/reproducibility exception, GX test behavior, provider assumptions recorded.** GX fixed (W-A3); DVC exception requested (A-02); Gemini lifecycle open (A-07).

## 5. `EvidenceBundle` v2 contract lock

### 5.1 Correction from W-A7 — separate `raw_features` from `accounting_profile`

W-A2 §3 currently sources `financial_ratios` from `compute_financial_ratios(raw_features)`. W-A7 proved that the 94 benchmark columns are **ratio-like**, not accounting amounts; the alias intersection with the 11 required inputs is empty, so every lookup falls back to `0.0`.

**Proposed correction (pending A-05):**

- Add `accounting_profile: dict[str, float] | None` — the 11 required inputs (`current_assets`, `current_liabilities`, `quick_assets`, `total_debt`, `total_equity`, `net_income`, `total_revenue`, `operating_profit`, `ebit`, `interest_expense`, `total_assets`), tagged `observed` or `synthetic`.
- `financial_ratios` is `derived` from `accounting_profile`, **not** from `raw_features`.
- `raw_features` remains the 94-feature Tier 1 model input only.
- Missing/invalid accounting inputs **fail validation**; no silent zero (D-01 / Option A). If `accounting_profile` is synthetic, the ratios are deterministic but inherit the upstream synthetic tag.

### 5.2 Seed-case set (proposed lock; pending A-05)

Four hand-authored cases, matching the capability-profile recommendation (one converge, two engineered-diverge, one low-confidence/missing-data). Values are representative; exact fixture values are authored in Wave C.

| Case | Intent | PD / rating / band | Accounting profile | Tier 3 fields | Expected verdict pattern | Expected label |
| --- | --- | --- | --- | --- | --- | --- |
| **SC-01** | Clear converge | PD < 2%; investment-grade; narrow band | Strong: CR ≈ 2.2, QR ≈ 1.8, D/E ≈ 0.35, NPM ≈ 12%, EBITDA ≈ 20%, ICR ≈ 8×, AT ≈ 0.9 | `covenant_flags=[]`, growth ≈ +8%, pipeline moderate, concentration `False` | CRO approve, Growth approve, Capital conditional/approve | `converge`; no escalation |
| **SC-02** | Diverge: Growth vs Risk | PD 3–6%; BB; moderate band | Weak: CR ≈ 0.9, QR ≈ 0.6, D/E ≈ 1.8, NPM ≈ 1%, EBITDA ≈ 6%, ICR ≈ 1.2×, AT ≈ 0.5 | covenant flags present, growth ≈ +35%, pipeline high, concentration `False` | CRO reject, Growth approve, Capital conditional | `diverge`; escalate |
| **SC-03** | Diverge: Capital vs Risk | PD 1–3%; BBB; low-moderate band | Strong: CR ≈ 1.9, QR ≈ 1.5, D/E ≈ 0.6, NPM ≈ 8%, EBITDA ≈ 15%, ICR ≈ 6×, AT ≈ 0.8 | `covenant_flags=[]`, growth ≈ +5%, pipeline moderate, concentration `True` (e.g. top customer 60%) | CRO approve, Growth conditional, Capital reject | `diverge`; escalate |
| **SC-04** | Incomplete / low confidence | PD 5–8%; B; wide band | Complete (ratios non-zero) | `covenant_flags=None`, `revenue_growth_rate=None`, `concentration_flag=None`; one persona invalid after bounded repair | CRO conditional (low confidence), Growth missing/invalid, Capital conditional (low confidence) | `incomplete`; HITL |

### 5.3 Acceptance criteria (v2 fixtures)

A v2 fixture is rejected when any W-A2 §4 condition holds, plus:

1. `financial_ratios` sourced from `raw_features` or from a missing `accounting_profile`.
2. The `financial_ratios` mapping is empty or all values are `0.0` (the R-01 seven-zeros case).
3. `p90_pd` is independently writable or differs from `pd_band.p90`.
4. `tail_loss_estimate` or `capital_consumption_estimate` appears.
5. A Tier 3 field is fabricated when its source is absent (SC-04 must surface `None`/incomplete, never a silent average).
6. A synthetic value lacks its `synthetic` tag/assumptions.

The offline harness (Wave C) replays **recorded** persona verdicts against the deterministic divergence/escalation function; it does not call an LLM. Exact divergence weights/thresholds remain evidence-gated (D-03) and are not fixed by this lock.

### 5.4 W-A2 open decisions resolved (recommendation)

- **`revenue_growth_rate` / `concentration_flag`:** SC-01–SC-03 supply them via the tagged synthetic profile; SC-04 deliberately uses `None`. Do **not** default them to `0.0`/`False`.
- **Capital rubric:** reword to `concentration_flag` + `p90_pd`/rating evidence (PD-based cost-of-capital proxy); do **not** retain `capital_consumption_estimate` as a synthetic field.

## 6. FR3 / `p90_pd` change note

The approved direction (§9.2) is already expressed as exact edits in [`evidence_bundle_v2_contract.md`](evidence_bundle_v2_contract.md) §5. **Not applied.** Three additions are required by Wave A evidence:

| Target | Current | Proposed |
| --- | --- | --- |
| `tier3_persona_architecture.md` §5 (schema sketch) | `recommendation: Literal["approve", "conditional", "decline"]` | `["approve", "conditional", "reject"]` (D-03 canonical; matches `src/schemas/evidence_bundle.py`) |
| `src/schemas/evidence_bundle.py` field docstring | `"Derived domain financial ratios computed from raw features"` | `"Derived from the validated accounting_profile; never from raw_features"` |
| W-A2 §3 `financial_ratios` row | `compute_financial_ratios(raw_features)` | `compute_financial_ratios(accounting_profile)` (see §5.1) |

The remaining rows (PRD FR3/rubric, tier3 §3–§4, ADR-026 body, README lines 37/67/96) are unchanged from W-A2 §5. Verify line numbers at application time; W-A2's citations predate the W-A3–W-A8 doc commits.

## 7. Decision register

Only the decisions Wave A evidence actually requires are listed. Everything else is record-only.

| ID | Decision | Recommendation | Evidence | Type |
| --- | --- | --- | --- | --- |
| **A-01** | Raw-row → Tier 2 input contract: **A** guard + **C** structured accounting profile, or **B** deterministic dataset→ratio mapping? | **A + C.** Fail loudly on missing accounting inputs; use the synthetic profile for ratio extraction. B is only valid with a semantically justified, deterministic mapping, which W-A7 did not find. | W-A7 §2/§6; D-01 | Owner decision (product/demo contract) |
| **A-02** | Install the proposed DVC graph? Provision the local remote or accept a re-acquire-and-verify exception? | **Install the draft; provision `../acras_dvc_remote`** (repo sibling; resolves to `C:\Users\sebas\Desktop\acras_dvc_remote` here). If unavailable, record the documented re-acquire + ADR-011 checksum exception. Do not switch to a cloud remote. | W-A8 §4–§5; D-09 | Owner decision (scope/remote) |
| **A-03** | Apply the Gemini pricing/cost correction: rates $0.30/$2.50, `output_billable = total − prompt`, `usage.details` passthrough? | **Approve as a Wave B change.** Current formula undercounts Gemini by ~4× input / ~8.3× output plus reasoning tokens. | W-A1 §4–§5 | Owner decision (formula/config) |
| **A-04** | Retain the frozen Tier 1 model or retrain on an independent final test? | **Retain.** CV Brier 0.022884 remains below 0.030; selection optimism 0.002118 is quantified; no retrain indicated. Disclose the CV Brier as the conservative estimate. | W-A5 §6; D-07 | Owner record (freeze/retrain branch) |
| **A-05** | Lock the v2 seed-case contract (§5) including the `accounting_profile` correction and SC-01–SC-04? | **Approve.** It decouples Tier 3 from upstream retraining/raw-row mapping and gives the Wave C harness a fixed target. | §5; W-A2; W-A7 | Owner approval (contract lock) |
| **A-06** | Apply the FR3 / `p90_pd` change note (W-A2 §5 + this package §6 additions) via change-management? | **Approve application.** Direction already approved 2026-10-20; this is the edit pass, not a new decision. | W-A2 §5; this package §6 | Change-management approval |
| **A-07** | Gemini 2.5 Flash lifecycle/deprecation is unverified. | **Bounded follow-up:** verify from a primary source before Phase 4 live reliance. A near-term date triggers the ADR-034 stop rule; no silent model swap. | W-A1 §6 | Follow-up evidence, not yet a decision |

## 8. Recommended next steps

1. **Owner acts on A-01…A-06.** A-07 is a bounded verification task.
2. **Apply A-06** (FR3/`p90_pd` change note) through change-management; verify the edited docs against §6.
3. **Wave B (only approved changes):** Gemini rates + cost formula + `details` passthrough (A-03); v2 schema with `accounting_profile` + required-input guard (A-01/A-05); install the DVC graph + commit `dvc.lock` (A-02).
4. **Wave C:** author the four seed fixtures + offline harness; then Phase 4 scope/spec and implementation-plan approval.
5. **Follow-up:** Gemini lifecycle verification (A-07); README `dvc pull` + PowerShell quickstart (A-02 companion).

## 9. Open evidence gaps

- **Gemini lifecycle/deprecation** — unverified (A-07). Live call works; near-term retirement cannot be ruled out.
- **Gemini AI Studio pricing page** — transport error; the $0.30/$2.50 figure is from Vertex, consistent with the live call.
- **Divergence formula/weights/threshold** — evidence-gated (D-03); the seed labels are relative (`converge`/`diverge`/`incomplete`), not numeric thresholds.
- **Qualitative grounding** — no LLM-judge evidence (D-06); numeric grounding only.
- **DVC remote** — absent; clean-clone `dvc pull` unsupported until A-02.
- **`PersonaVerdict.limitations`** — still a Phase 4 candidate (W-A2 §6), not part of this lock.

## 10. Minor corrections

- **W-A5 terminology:** the 3.47% figure is the **mean predicted PD**, not the observed base rate. The test set has 1,364 rows / 44 defaults → observed base rate **3.2258%**. The δ\* shift and Brier/AUC results are unaffected; the post-shift mean PD is 3.47% + 4.10% = 7.57%.
- **W-A2 source line:** `financial_ratios` is corrected to `accounting_profile` (§5.1); the v2 contract table should be read with this correction.
- **Tier 3 doc drift:** `decline` → `reject` (D-03), added to the change note (§6).
