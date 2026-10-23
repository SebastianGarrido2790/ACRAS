# EvidenceBundle v2 Contract — Field & Provenance Table (W-A2)

*ACRAS · 2026-10-23 · Wave A W-A2 · contract deliverable (measure-only; no code or schema change applied).*
*Source: [`execution_plan.md`](execution_plan.md) §2 W-A2 · authority: [`remediation_plan.md`](remediation_plan.md) §3 (D-01/D-10) and §9.2 (approved FR3/`p90_pd` resolution).*

This document is the **change-note ready for owner sign-off** required before any Phase 4 candidate is accepted. It pins, field by field, the provenance of every `EvidenceBundle` v2 field and applies the approved loss-denominated-field resolution. The edits it authorizes (once signed) are listed in §5 and proceed through change-management; they are **not applied by this Wave A task**.

## 1. Provenance taxonomy

| Tag | Meaning | Rule |
| --- | --- | --- |
| `observed` | Read directly from a validated source (identifier, verified benchmark feature, profile fact). | Never transformed into a different quantity without a documented mapping. |
| `derived` | A deterministic function of other fields (INV-1). | Reproducible; must not take LLM output as input; must validate its required inputs. |
| `synthetic` | A supplied value with tagged assumptions, not computed. | Must carry its assumptions; must never be presented as calculated. |

Cross-cutting rules (D-01/R-01, and "Decisions that do not need owner input" §3):
- **No silent zero.** A missing required source field fails validation; it is never substituted as `0.0`.
- **Loss fields are a set.** All loss-denominated fields are excluded by default; none is retained as a synthetic value unless the consuming rubric is reworded (approved FR3 resolution #1).
- **Bind, don't copy.** `p90_pd` references `pd_band.p90`; it is not an independently settable value.
- **INV-1 boundary.** `persona_verdicts` (LLM output) never feeds a `derived` field or any Tier 1/2 calculation.

## 2. Loss-denominated field disposition (decided as a set)

| Field | Disposition | Rationale | Consuming rubric | Rubric action |
| --- | --- | --- | --- | --- |
| `tail_loss_estimate` | **Exclude** | LGD/EAD and risk-weight source absent; described as "derived from P90 band" but no loss calculation exists. | CRO (§3) | CRO's quantitative field becomes `p90_pd` (scenario-conditional PD). |
| `capital_consumption_estimate` | **Exclude** | Same LGD/EAD and risk-weight dependency (FR3 amendment 1). | Capital (§3) | Capital's field becomes `concentration_flag` + `p90_pd`/rating evidence (PD-based cost-of-capital proxy). |

Neither field is retained as `synthetic`, because the approved resolution defaults to exclusion and the consuming rubrics are reworded rather than fed an uncomputable estimate.

## 3. `EvidenceBundle` v2 field contract

Legend — provenance: O=observed, D=derived, S=synthetic. Optional fields default to `None` when their source is absent.

| Field | Tier / owner | Prov. | Source / formula | Units | Assumptions / label | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| `company_id` | — | O | Verified entity identifier. | — | Unique per bundle. | Non-empty (`min_length=1`). |
| `raw_features` | Tier 1 input | O | Validated benchmark features (94 canonical inputs after ADR-024). | mixed | Model features, **not** financial-statement line items or deal facts. | Non-empty mapping of finite `float|int`. |
| `schema_version` | — | D | Version tag (`"v2"`). | — | — | Literal set; v2 enforces the v2 contract. |
| `pd` | Tier 1 | D | Calibrated ML probability of default. | [0,1] | Calibration per ADR-021. | Finite, in `[0.0, 1.0]`. |
| `credit_rating` | Tier 1 | D | `pd` → rating bracket via `rating_thresholds`. | — | Deterministic mapping. | Member of `VALID_CREDIT_RATINGS`. |
| `pd_band.p10/.p50/.p90` | Tier 2 | D | Vectorized Monte Carlo (FR3), $N\ge10^4$. | [0,1] | **Scenario-conditional PD percentiles under assumed parameters (R-09)** — never loss estimates or model-estimation confidence intervals. | Finite; monotone `p10 ≤ p50 ≤ p90`. |
| `financial_ratios` | Tier 2 | D | `compute_financial_ratios(raw_features)` (FR5). | ratio | Deterministic ratio computation; aliases must map to present keys. | Non-empty; every value a finite float; **no silent zero for missing keys** (R-01). |
| `p90_pd` | Tier 3 (CRO) | D | **By reference**: `p90_pd := pd_band.p90`. | [0,1] | Scenario-conditional PD under assumed parameters (R-09). | Enforced equal to `pd_band.p90`; **not an independent writable value** (no duplicate). |
| `pd_tail_spread` | — | — | `p90_pd − pd_band.p50`. | [0,1] | **Not added**: no rubric consumes it. | Deferred candidate (add only if a rubric consumes it). |
| `covenant_flags` | Tier 3 (CRO) | S | Qualitative risk flags from the structured company profile. | — | Synthetic; tagged "profile-supplied, not observed". | `list[str]` or `None`; never computed. |
| `revenue_growth_rate` | Tier 3 (Growth) | S (D) | Profile-supplied; if both `revenue_t` and `revenue_{t-1}` are present and finite, `derived = rev_t/rev_{t-1} − 1`. | ratio | Synthetic unless a deterministic revenue series exists. | Finite or `None`; no fabrication. |
| `pipeline_value_estimate` | Tier 3 (Growth) | S | Deal/pipeline value from the profile. | currency | Synthetic; tagged assumptions. | `float` or `None`; never computed. |
| `concentration_flag` | Tier 3 (Capital) | S | Customer/revenue concentration flag from the profile (or derived if concentration inputs exist). | — | Synthetic (or derived with documented inputs). | `bool` or `None`. |
| `persona_verdicts` | Tier 3 | D | Structured persona output via gateway (INV-6). | — | LLM-generated; never feeds a `derived` field (INV-1). | Each value validates against `PersonaVerdict` (`approve`/`conditional`/`reject`). |
| `tail_loss_estimate` | — | — | **Excluded** (see §2). | — | — | Must not appear in v2. |
| `capital_consumption_estimate` | — | — | **Excluded** (see §2). | — | — | Must not appear in v2. |

## 4. Schema validation acceptance criteria (falsification)

A `v2` fixture is rejected when any of the following hold:

1. **Missing provenance** — a field with no source/units/provenance entry in §3.
2. **Non-finite ratio** — any `financial_ratios` value is non-finite or non-`float`.
3. **All-zero `financial_ratios`** — the mapping is empty or every value is `0.0` (the R-01 seven-zeros case).
4. **Loss-denominated field present** — `tail_loss_estimate` or `capital_consumption_estimate` appears (they are excluded as a set).
5. **Duplicated `p90_pd`** — `p90_pd` is an independently settable value that can diverge from `pd_band.p90`; v2 must derive it by reference only.
6. **Loss/uncertainty language** — `pd_band` or `p90_pd` is labelled as a loss estimate or model-estimation confidence interval (must be "scenario-conditional PD under assumed parameters (R-09)").
7. **Silent zero** — a required source field is missing and silently treated as `0.0` instead of failing.

## 5. Change-note — exact edits for owner sign-off (change-management, not applied here)

| Target | Current | Proposed |
| --- | --- | --- |
| `reports/docs/groundedness/prd.md` line 56 (FR3) | "producing P10/P50/P90 default/loss bands" | "producing P10/P50/P90 default-probability bands; loss bands are deferred until LGD/EAD are in scope." |
| `reports/docs/groundedness/prd.md` line 125 (rubric) | "CRO weighted toward P90 tail loss and covenant history" | "CRO weighted toward `p90_pd` (scenario-conditional PD) and covenant history." |
| `reports/docs/architecture/tier3_persona_architecture.md` §3 (Capital row) | "Capital-consumption estimate, concentration flag" | "concentration flag and `p90_pd`/rating evidence (PD-based cost-of-capital proxy)." |
| `reports/docs/architecture/tier3_persona_architecture.md` §3 (CRO row) | "P90 loss band, covenant/qualitative risk flags" | "`p90_pd` (scenario-conditional PD), covenant/qualitative risk flags." |
| `reports/docs/architecture/tier3_persona_architecture.md` §4 (field list) | `tail_loss_estimate` and `capital_consumption_estimate` listed | Remove both; add `p90_pd` (reference to `pd_band.p90`). |
| `reports/docs/architecture/system_design.md` §6 ADR-026 body | "P90 loss distribution / tail-loss interpretation" | Restate as PD-percentile interpretation with the R-07 "no removal without provenance" rationale. |
| `README.md` lines 37/67 | "P10/P50/P90 loss and default bands" / "Loss & Default Distributions" | "P10/P50/P90 default-probability bands" (loss deferred). |
| `README.md` line 96 (persona rubric) | "tail loss, covenants" | "`p90_pd` (scenario-conditional PD), covenants". |

## 6. Versioning and ADR gate

- `schema_version` gains `"v2"` under the existing ADR-014 sequence; the v2 contract above replaces the v1 Tier 2/3 field set once signed and implemented.
- The `PersonaVerdict.limitations` addition (tier3 §5) is **not** part of this W-A2 decision; it remains a Phase 4 candidate.
- An ADR-016 entry is offered only if the signed contract passes the three ADR-threshold tests in `remediation_plan.md` §2; this table alone does not create the ADR.

## 7. Open decisions for owner

- `revenue_growth_rate` and `concentration_flag` are marked synthetic-by-default for the 3–5 seed cases because the benchmark dataset carries no revenue-series or concentration inputs. Confirm the seed cases will supply these via the synthetic profile, or accept `None` for those fields.
- Confirm the Capital rubric rewording (§5 row 3) rather than retaining `capital_consumption_estimate` as a synthetic field.
