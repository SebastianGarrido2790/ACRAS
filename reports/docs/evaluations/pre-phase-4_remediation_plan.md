# Pre-Phase-4 Remediation Plan — ACRAS

*· v1.2 · **Owner decision recorded 2026-10-20: D-01 through D-11 approved; v1.2 adds the Wave A work order, Gate R decoupling split, D-1.12 rationale correction, R-06 gate-sensitivity test, R-07 Yeo-Johnson check, R-10 copy-rate flag, and R-15 GX test-mutation fix.** Rejected alternatives and their trade-off text are retained unedited for traceability (§7, §9).*

## 1. Purpose, scope and limits

This draft answers: **before writing Phase 4 code, what must be decided, and why?** It converts verified findings into bounded decision questions, recommended go-tos, and evidence tests where the best option is not yet established. All recommendations were approved as recorded in §9. Approval fixes the go-to and its stated sequencing only; it does not authorize implementation, and Phase 4 planning remains a separate approval.

**Evidence reviewed.** `data/raw/data.csv` has 6,819 rows, one target plus 95 features, 220 positive labels, and no blank fields. The 94-feature canonical Tier 1 schema, training/selection code, promotion gate, Tier 2 ratio extraction and simulation, EvidenceBundle v1, gateway, ADR-027, project invariants, Tier 3 architecture, PRD, roadmap, capability-profile gates, and Phase 3 closure evidence were inspected. The full automated suite reports 191 passed and 4 skipped; the skips are three Docker-daemon-dependent integration cases and one opt-in live-provider smoke test. A source-level local run confirmed that passing a dataset row to the current Tier 2 ratio extractor yields seven zero ratios. Claims below distinguish verified repository facts from proposals and external facts that remain to be checked. No external pricing or provider-lifecycle lookup was performed.

**Primary evidence trail.** [Raw dataset](../../../data/raw/data.csv), [feature schema](../../../src/schemas/features.py), [training/selection code](../../../src/pipelines/training/train.py), [promotion gate](../../../src/pipelines/training/promotion_gate.py), [Tier 2 service](../../../src/tier2_simulation/service.py), [ratio extraction](../../../src/tier2_simulation/ratios.py), [simulation engine](../../../src/tier2_simulation/engine.py), [EvidenceBundle](../../../src/schemas/evidence_bundle.py), [DVC pipeline](../../../dvc.yaml), [parameters](../../../params.yaml), [system design and ADRs](../architecture/system_design.md), [Tier 3 persona architecture](../architecture/tier3_persona_architecture.md), [PRD](../groundedness/prd.md), [capability-profile gates](capability_profile_gates.md), and [Phase 3 closure evidence](../phases/phase_3/implementation_plan.md).

## 2. Priority and sizing

- **P0:** Phase 4 would be unsound or unfalsifiable without it.
- **P1:** weakens the deterministic core that Tier 3 consumes; may force a Tier 1 retrain.
- **P2:** hygiene that is cheaper to fix before Tier 3 code exists.
- **Sizing:** effort is TBD (to be determined) until the owner selects scope and approach; this draft does not make schedule commitments.
- **Decision status:** "Owner decision" means approval is required; "Record-only" means project constraints already determine the go-to; "Evidence first" means run the bounded qualification test before asking the owner to choose.
- **Approval (2026-10-20):** every listed decision is **approved**, including the stated sequencing. For evidence-first items, approval covers the go-to and the requirement to complete the bounded test; the dependent choice is not pre-empted where the recommendation explicitly defers it.
- **ADR threshold:** offer an ADR only when all three tests pass: (1) the choice is hard to reverse at meaningful cost; (2) a future reader would find it surprising without recorded rationale; and (3) materially viable alternatives existed and one was selected for specific trade-offs. If any test fails, record the choice in the relevant specification, implementation plan, evaluation, or existing decision record instead. An ADR is never implied merely because a change is architectural or consequential.

## 3. Decisions before code

| ID | Question that must be answered | Recommended go-to | Why / trade-off | Status |
| --- | --- | --- | --- | --- |
| D-01 / R-01 | What inputs may Tier 2 and Tier 3 treat as observed, derived, or synthetic evidence? | Keep benchmark model features distinct from financial-statement/deal inputs; reject unsupported calculations rather than substitute zero. Mark every synthetic value and define derivation provenance. | The checked-in rows do not provide the accounting amounts and deal facts expected by the ratio/persona contracts. A mapping is only valid if it is deterministic and semantically justified; direct reuse is simpler but currently produces invalid zero ratios. | **APPROVED 2026-10-20** — Owner decision on product/demo input contract; rejection of missing required inputs is record-only. |
| D-02 / R-02 | Do analyst nodes have a unique responsibility beyond the existing Tier 1/Tier 2 outputs? | Remove duplicate rating/ratio computation; retain a deterministic node only if it has a named, non-duplicated assembly or validation contract. | Removing duplicate work is simpler and avoids implying LLM authority over deterministic calculations. A distinct assembly node may help graph clarity but needs an explicit interface and measurable purpose. | **APPROVED 2026-10-20** — Owner decision. |
| D-03 / R-03 | What structured verdict fields and rubric determine divergence and escalation? | Use canonical `approve` / `conditional` / `reject` values; calculate divergence deterministically over recommendation, anchored lean, and persona confidence as INV-4 requires. Keep persona confidence distinct from Tier 1 confidence. | Determinism and all three structured fields are required by INV-4, and canonical vocabulary avoids schema drift. Confidence semantics/weighting, Tier 1 confidence proxy, and thresholds need evidence; selecting them now would be arbitrary. | **APPROVED 2026-10-20** — Owner decision on formula and threshold; confidence semantics and Tier 1 confidence proxy remain evidence-first. |
| D-04 / R-04 | What minimum case set and evidence make Phase 4 exit falsifiable? | Use the owner-approved 3–5-case smoke set; treat it as a development check, not a statistical claim. Pair divergence detection with false-escalation/convergence reporting. | The 12-case alternative was not approved and lacks a stated coverage need. A smoke set keeps cost small; it cannot establish population performance. | **APPROVED 2026-10-20** — Owner decision on scope/exit criteria. |
| D-05 / R-05 | Which orchestration and output-validation path meets the contract within bounded cost/latency? | Prefer gateway-direct LangGraph calls with Pydantic validation if a short gateway-level qualification confirms structured-output support; otherwise leave unresolved until adapter evidence is compared. | Direct calls minimize dependencies; a gateway-backed Pydantic AI adapter may simplify typed model integration but adds an adapter boundary. Provider capability must be tested through the configured gateway, not inferred from provider documentation alone. | **APPROVED 2026-10-20** — Evidence first, then owner decision if both paths remain viable. |
| D-06 / R-05 | How should report grounding and partial/fallback failures affect the final result? | Deterministically validate all report numbers against the evidence bundle; on missing persona output or invalid verdict after one bounded repair, return an incomplete result for human review. Qualitative grounding remains an evidence-test question. | Numeric checks are reproducible and inexpensive. An LLM judge could assess qualitative claims but adds cost and false-positive/negative risk; it must never calculate divergence. Whether fallback near a threshold forces HITL needs an explicit policy. | **APPROVED 2026-10-20** — Record-only for incomplete results; evidence first for qualitative grounding; owner decision on fallback-triggered HITL. |
| D-07 / R-06 | Is the frozen Tier 1 artifact retained with its disclosed evaluation limitation, or retrained using an independent final test? | Quantify the selection effect first; do not retrain or change the promotion gate until evidence and owner approval. | The current held-out set was used to rank candidates, so its winning metrics are not an independent final estimate. Retraining may improve validity but costs time and may change serving behavior. | **APPROVED 2026-10-20** — Evidence first, then owner decision. |
| D-08 / R-07 | Does new feature evidence justify changing the handling already governed by ADR-026? | Preserve the accepted no-removal/no-winsorization policy unless authoritative provenance and measured evidence justify requesting a superseding decision. | Extreme magnitude alone does not establish corruption. Changing feature handling can invalidate model behavior and requires impact assessment; retaining the current policy avoids unsupported changes. | **APPROVED 2026-10-20** — Record-only under current constraints; any exception requires owner decision. |
| D-09 / R-08 | How much reproducible Tier 1 lineage is required before Phase 4? | Propose an end-to-end DVC stage design and clean-environment evidence; keep the accepted local remote unchanged unless the owner separately approves a remote/setup change. | The current DVC pipeline does not reproduce training/promotion. Extending lineage improves auditability; clean-clone retrieval may require a remote decision beyond Phase 4 code. | **APPROVED 2026-10-20** — Evidence first; owner decision on any scope/remote change. |
| D-10 / R-09 | What do Tier 2 percentiles mean, and should configured shock parameters affect them? | Label current outputs as simulated PD percentiles, not losses or model-confidence intervals. Measure parameter usage and sensitivity before changing the engine. | Output relabeling corrects interpretation without changing behavior; activating unused parameters changes model semantics and needs evidence plus approval. | **APPROVED 2026-10-20** — Output naming is record-only; parameter behavior is evidence-first then owner decision. |
| D-11 / R-10–R-14 | Which operational or hygiene items are necessary for this phase rather than merely desirable? | Verify pricing/model lifecycle and identify reproducibility gaps; defer tooling, broad documentation cleanup, and remote changes unless the approved Phase 4 scope depends on them. | This limits work to Phase 4 prerequisites and avoids expanding scope based on hypothetical risks. | **APPROVED 2026-10-20** — Evidence first for factual claims; owner approval for scope or behavior changes. |

### Decisions that do not need owner input under current constraints

- Missing or semantically unsupported source fields must not silently become numeric zero. Require explicit validation/failure; this is the only safe interpretation of the current typed-contract and deterministic-core constraints.
- Tier 2 P10/P50/P90 outputs must not be described as loss estimates or model-estimation confidence intervals unless the underlying calculations and inputs are changed and approved.
- All persona calls continue through the gateway circuit breaker; no direct provider-SDK path is an option.
- Persona failure cannot be represented as a complete three-persona result. The system must surface incomplete analysis for human review rather than silently average the remaining opinions.
- INV-4 requires deterministic divergence over `recommendation`, `lean`, and persona `confidence`; confidence semantics/weighting may be evidence-gated, but excluding that field is not an open design branch. Low, uniform persona temperature is also fixed by INV-5.

### Phase 4 candidate feature register

These candidates are derived from PRD FR1–FR9, Phase 4 roadmap capabilities, the verified current-state gaps in this document, and the governing ADRs/invariants. They are **candidates, not accepted Phase 4 scope**: approval of D-01–D-11 approves decision directions, not feature inclusion or implementation. Each depends on separate Phase 4 scope/spec approval.

| Candidate | Outcome and boundary | Traceability | Current-state evidence and dependencies | Acceptance evidence | Disposition / SDD |
| --- | --- | --- | --- | --- | --- |
| `p4-evidence-contract` | Define validated Tier 3 evidence inputs and provenance across existing Tier 1/Tier 2 output and persona-only context. Keep benchmark features distinct from financial/deal facts; make unsupported dataset-to-ratio use explicit and reject it unless a valid deterministic mapping is defined; mark synthetic values. No dashboard or invented LGD/EAD calculation. | PRD FR1–FR5; INV-1/2; ADR-002/033; approved D-01/D-10. | EvidenceBundle v1 exists, but passing the benchmark row to ratio extraction currently produces seven zeros. Tier 1/Tier 2 are implemented; the Tier 3 field/source contract is not. Depends on field/source inventory and deterministic Tier 2 outputs. | Schema/contract tests reject missing or unsupported required inputs; every field has source, units, provenance and validation; no LLM output enters calculation inputs; derived values are reproducible. | Candidate; accept only after Phase 4 scope approval. Include as a contract section in the integrated Phase 4 spec rather than creating a separate feature spec by default. |
| `p4-persona-interpretation` | Run the CRO, Growth, and Capital personas in parallel over the same typed evidence, with role-conditioned rubrics and a validated structured verdict. No duplicate rating/ratio analysts, peer-output context, or persona tool authority. | PRD FR6; INV-5/8; ADR-005/008; approved D-02/D-03; Tier 3 persona architecture. | Persona architecture and verdict schema are proposed/existing contracts, but persona workers are not implemented; gateway is already available from Phase 3. Depends on `p4-evidence-contract` and the existing gateway. | Graph tests prove parallel independent invocations share the approved evidence contract; each output validates against the canonical verdict schema (`approve` / `conditional` / `reject`); temperature is uniform and role framing remains CRO/Growth/Capital. | Candidate; scope pending. One cohesive Phase 4 spec should cover the three personas rather than one feature/spec per persona. |
| `p4-convergence-escalation` | Reconcile the three structured verdicts, compute deterministic divergence, and route cases to human review under approved escalation rules. No narrative LLM judge for divergence and no automatic loan approval. | PRD FR7/8; INV-4/9/10; ADR-004; approved D-03/D-06. | Divergence calculation and convergence node are not implemented. Formula, persona-confidence semantics, Tier 1 confidence proxy, and thresholds still need bounded case evidence. Depends on `p4-persona-interpretation`; persona confidence must remain in the divergence function under INV-4 and is distinct from Tier 1 confidence. | Unit/property tests cover all structured verdict fields, permutation invariance, threshold boundaries, low Tier 1 confidence, incomplete/invalid personas, and human-routing outcomes; no case is silently auto-resolved. | Candidate; scope pending. Formula/threshold decisions remain evidence-gated even though the governing direction is approved. |
| `p4-report-orchestration` | Assemble the evidence, persona verdicts, deterministic convergence result, and auditable executive report; enforce bounded failure behavior and numeric grounding. Consume Phase 3 gateway/fallback rather than rebuilding it. | PRD FR9; Phase 4 roadmap; INV-2/6/10; ADR-002/006/034; approved D-05/D-06. | Phase 3 gateway has bounded primary/fallback handling and provider events; no Tier 3 orchestration/report assembly exists. Depends on the previous candidates and gateway structured-output qualification. | End-to-end tests cover successful report, numeric consistency with the evidence bundle, schema/repair exhaustion, partial persona failure, and fallback provenance; failures produce an explicit incomplete/HITL result. Measure PRD latency and cost budgets. | Candidate; scope pending. Include in the integrated Phase 4 spec; do not create a separate feature solely for logging or retry details. |

**Phase boundary.** The 3–5-case seed set is acceptance evidence for these candidates, not a separate product feature. The full golden dataset and automated Tier 3 promotion gate belong to the Phase 5 roadmap; FR13 still prohibits Tier 3 promotion to serving until that gate exists and passes. Do not add dashboard work (Phase 6), rebuild the Phase 3 gateway, or promote Tier 3 in Phase 4. Tier 1 retraining, broad feature-policy changes, DVC pipeline expansion, and general tooling/documentation cleanup are readiness/remediation work, not Phase 4 candidate features unless evidence establishes a blocking dependency. One integrated Phase 4 SDD spec is the recommended minimum; split feature specs only if the approved scope reveals independent deliverables.

**Open requirement reconciliation before candidate acceptance (real Phase 4 blocker):** PRD FR3 says Tier 2 produces default/loss bands, and `tier3_persona_architecture.md` (§3–§4) names `tail_loss_estimate` (described as derived from the P90 band) as the CRO persona's primary weighted field. Meanwhile, the implemented Tier 2 engine produces `PDBand(p10, p50, p90)` default-probability percentiles and no LGD/EAD loss calculation exists. Approved D-10 requires labeling current outputs as simulated PD percentiles; it does not by itself amend FR3 or the CRO field name. **Proposed resolution (for owner decision):** rename CRO's primary quantitative field from `tail_loss_estimate` to a PD-denominated field (`p90_pd` / `pd_band.p90`, paired with `pd_tail_spread = pd_band.p90 - pd_band.p50` if a spread metric is desired) and record a change-management clarification to PRD FR3 that Tier 2 outputs P10/P50/P90 PD bands (loss bands require LGD/EAD inputs that are out of scope unless separately specified). Resolve this before accepting any Phase 4 candidate.

## 4. Detailed evidence and options

### P0 items

### R-01 · Input contract and derived-field provenance

**Finding.** Verified: the dataset supplies 95 ratio-like features (94 canonical Tier 1 inputs after ADR-024), not financial statement line items, loan terms, sector, or covenant history. The PRD expects synthetic structured company profiles for production/demo input; that is not the same contract as the benchmark dataset row. More urgently, `run_simulation_pipeline` passes `EvidenceBundle.raw_features` directly to `compute_financial_ratios`, whose aliases expect underlying accounting amounts (for example `current_assets` and `current_liabilities`) and silently use zero for missing keys. A raw dataset row therefore currently produces seven all-zero `financial_ratios`. The v1 evidence schema requires a non-empty mapping but does not reject those semantically invalid zeros. The Tier 3 design also lists proposed fields (tail loss, capital consumption, concentration, covenant flags, growth, pipeline) without an implemented source/formula contract. The current engine returns PD bands, not loss bands; no LGD/EAD loss calculation was found.

**Action.**

1. Resolve the input-contract mismatch before choosing a UI/demo path: document the distinction between the model's 94 benchmark features and the PRD's synthetic structured profile. Compare a dataset-row/ratio input path with statement-field inputs and a deterministic, validated mapping; state what each can and cannot establish.
2. Specify every EvidenceBundle v2 field with its source, formula, owner, units, assumptions, validation, and whether the value is observed, synthetic, or derived. Do not call PD percentiles loss estimates; add LGD/EAD or other economics only if the human-approved scope requires them and their inputs are defined.
3. Correct the dataset-row ratio path: either provide compatible source fields and explicit required-input validation, or map/rename the fields only under an approved, documented derivation. Missing source data must not silently become a plausible zero.
4. Define golden/demo-case construction and provenance. Perturbing real rows is one candidate for model-feature coverage, but cannot by itself supply deal terms or qualitative facts; label any synthetic additions and do not treat them as observed data.

**Done when.** The input contract and field table have human approval; tests prove required source inputs, reject unsupported/missing data, and establish deterministic-only lineage for calculation fields (INV-1). Any decision to change an existing interface or model input contract follows change management.

**Record.** Capture the approved field contract in its schema/specification and configuration where applicable. Offer ADR-016 only if the selected contract passes all three ADR-threshold tests in §2; do not create a configuration block for fields whose definitions remain undecided.

### R-02 · Reconcile planned analyst-node responsibilities

**Finding.** These are planned documentation components, not implemented agents (`src/agents/` contains package skeletons). The architecture's data-flow text assigns rating to a Data Scientist Agent although the serving/Tier 1 path already supplies rating; it assigns ratio computation to a Financial/Domain Analyst Agent although the Tier 2 service already computes ratios. FR5 and ADR-033 require deterministic ratio computation, not an LLM agent. The persona architecture still describes these analyst agents as workers, so the intended component boundary is inconsistent.

**Options.** A: remove redundant analyst-agent steps and have orchestration consume Tier 1/Tier 2 outputs. B: retain named deterministic orchestration nodes if they perform an explicit, non-duplicated contract/assembly responsibility. The existing docs do not establish a need for B.

**Done when.** The human-approved component boundary is consistent in the Tier 3 architecture and system data flow; a graph/contract test confirms that only the three persona nodes make LLM calls and that all calculations remain deterministic.

**Record.** Update the affected architecture/data-flow documents after approval. Offer an ADR only if the selected boundary passes all three ADR-threshold tests in §2; this draft does not authorize removing or adding a node.

### R-03 · Divergence and escalation specification

**Finding.** The deterministic divergence function is specified but not implemented. The structured `PersonaVerdict` model exists, but it has no anchored `lean` rubric; `confidence` is persona-reported, while the separate "Tier 1 confidence" required by FR8/INV-9 has no definition. There is also a contract mismatch: the implemented Pydantic schema uses `reject`, while the persona-architecture example says `decline`; the PRD uses `reject`. The threshold remains provisional.

**Action.**

1. Define persona-specific `lean` anchors and examples; align the recommendation vocabulary to the existing canonical `approve` / `conditional` / `reject` contract unless the owner approves a versioned change.
2. Implement and document the deterministic formula over all invariant-required structured fields: `recommendation`, `lean`, and persona `confidence`. Establish confidence semantics and any weighting with case evidence; removing the confidence field would require an explicit invariant change, not an ordinary schema decision.
3. Define Tier 1 confidence as a deterministic function of Tier 1/2 outputs only. Candidate proxies include distance to a rating threshold and relative PD-band width; decide whether either is valid before selecting and calibrating a threshold. Do not use persona-reported confidence as a substitute.
4. Write the escalation truth table: divergence above threshold, low Tier 1 confidence, any persona failure, schema-invalid output, fallback-served verdict (see R-05).

**Done when.** Pure functions have unit and property tests (invariant under persona permutation; monotonic in lean spread); every truth-table row is tested.

**Record.** Record approved formula, thresholds, and escalation behavior in the relevant contract/specification; clarify PRD FR7/FR8 through change-management. Offer an ADR only if the approved design passes all three ADR-threshold tests in §2.

### R-04 · Seed golden set and falsifiable Phase 4 exit

**Finding.** The roadmap's Phase 4 exit criterion ("genuinely different verdicts") is qualitative, while the fuller golden-set evaluation is scheduled for Phase 5. The PRD/capability-profile documentation already proposes a 20–40-case set and a 3–5-case Phase 4 seed set; the roadmap does not include the seed set. A divergence-recall-only metric would reward always-escalate behavior, so it needs a converge/false-escalation countermetric. Rubrics and labels authored by one person also limit independence. Hosted-model repeatability cannot be guaranteed by temperature alone.

**Action.**

1. Use the owner-approved 3–5-case Phase 4 seed set. The larger 12-case alternative was not approved. Keep the seed set as a development smoke test, not a statistical claim.
2. Report divergence recall and false-escalation rate on converge cases, with per-case verdicts and the exact escalation rule.
3. Identify and freeze hold-out cases before rubrics are tuned; set the proportion after the case count and coverage rationale are approved.
4. Consider a bounded repeatability protocol (for example, repeated calls on a subset per provider); report recommendation flip rate and divergence-score variation. This would supplement—not silently replace—the ADR-005 fixed-settings regression.
5. Run every case on the primary and on forced fallback.
6. Use verified model rows only for the features they contain; explicitly label synthetic deal terms and qualitative fields (R-01).
7. Put any approved Phase 4 exit-criterion change in its implementation plan; the roadmap is a sequencing artifact, not the authority for technical detail.

**Done when.** The seed set is versioned with labelled expectation and rationale per case; the harness runs offline from recorded responses and live; baseline numbers are recorded with no threshold claimed until Phase 5.

**Record.** Record the smoke set and its limits in the evaluation specification; keep the scoping document's §9 divergence target provisional until supported by evidence and approved. Offer an ADR only if the chosen evaluation protocol passes all three ADR-threshold tests in §2; adding a test alone does not qualify.

### R-05 · Orchestration contract and failure semantics

**Finding.** Phase 3 provides a generic gateway and bounded primary/fallback handling, not a `PersonaVerdict` schema-constrained interface. Its no-same-provider-retry policy is explicit; the Tier 3 repair/retry policy is not. The design documents do not settle partial-persona failure, fallback provenance, or whether a fallback verdict changes HITL behavior. Gemini and Groq use different models, so semantic equivalence is not guaranteed (Phase 3 explicitly disclaims it). The PRD/capability design proposes LLM-as-judge grounding, while deterministic numeric validation is another viable control; INV-4 prohibits LLM judging for divergence, not generally for grounding. Treat the grounding mechanism and its role as an open design decision, not an invariant violation.

**Action.**

1. Test each provider's actual structured-output support through the gateway with a bounded, documented sample; record schema-valid rate, latency, and provider-reported usage. Do not assume a provider's feature works through the configured endpoint.
2. Integration decision. A (recommended): LangGraph nodes call the gateway directly and validate with Pydantic v2; no Pydantic AI in the Tier 3 path. B: Pydantic AI with a gateway-backed model adapter.
3. Failure table. Persona failure: no report; escalate as incomplete (never average two personas). Schema-invalid: at most one bounded repair re-ask through the gateway, counted against the call budget, then fail. Fallback-served: verdict tagged with provider; decide whether a fallback verdict near the threshold forces HITL.
4. Decide the grounding control: compare deterministic validation of report numbers against bundle fields with the existing LLM-judge proposal, including false positives/negatives and whether either blocks a report. Keep report numbers template-bound where feasible.

**Done when.** Provider capability evidence and an approved failure/grounding contract are recorded; failure rows are tested with mock transport, and the selected grounding check has falsification tests.

**Record.** Record the selected contract and failure table in the Phase 4 specification/plan. Offer an ADR only if the selected orchestration choice passes all three ADR-threshold tests in §2.

### P1 items

### R-06 · Tier 1 gate-strength and selection-leakage audit

**Finding.**

- `brier_threshold: 0.030` is close to the no-skill baseline: with a 3.23% base rate (220/6,819), predicting the base rate gives a Brier of about 0.0312, so the gate demands only about 3.9% skill.
- The test split holds about 44 positives, so Brier and reliability estimates are noisy.
- `train_and_evaluate_all_models` evaluates all 12 candidates on the held-out test set and sorts them by test Brier score; ADR-027 reports the winning candidate's test metrics. The test set therefore participated in model selection and is not an independent final evaluation set for the selected winner.
- Isotonic calibration on about 176 training positives can be step-shaped and unstable.
- The gate applies a Brier threshold plus an AUC threshold. Training code computes calibration-curve diagnostics, but there is no separate reliability-curve acceptance criterion; clarify whether INV-3/ADR-003's wording intends one.

**Action.** First quantify both the selection effect and the promotion gate's **calibration sensitivity**:
- **Gate sensitivity check (Wave A):** apply controlled monotone distortions to the promoted model's predicted probabilities—specifically a logit shift $p'(\delta) = \sigma(\operatorname{logit}(p) + \delta)$ (calibration-in-the-large) and a logit scale / power distortion $p'(\gamma) = \sigma(\gamma \cdot \operatorname{logit}(p))$ (calibration slope)—and record the exact distortion magnitude ($\delta^*$, $\gamma^*$, induced mean-PD shift, and reliability-bin ECE) at which `brier_threshold: 0.030` first trips while ROC-AUC stays invariant. This measures the smallest miscalibration the current gate can detect (INV-3) and provides a quantitative basis to decide whether an explicit reliability-curve criterion is needed.
- **Selection-leakage quantification (Wave A):** quantify the optimism from ranking the 12 candidates on the held-out test set and document the validity limit of the reported test metrics.

Then present a human decision on whether to retain the frozen artifact with that caveat or retrain under a corrected evaluation protocol. If retraining is authorized:

1. Select candidates using training-only cross-validation (nested CV if using the same data to tune and estimate generalization); reserve a test set that is consulted once after selection.
2. Report Brier, Brier skill score against the training base rate, AUC/KS, reliability curve and uncertainty intervals; quantify calibration uncertainty given the small positive count.
3. Compare Platt and isotonic calibration inside the selection procedure, not by choosing from final-test outcomes.
4. Update the promotion gate only after measured baselines and human approval; keep Brier and discrimination checks and decide explicitly whether a reliability criterion is also required.

**Done when.** The selection leakage is disclosed in an evaluation report and the owner records a freeze/retrain decision. Any replacement model has a valid final evaluation, promotion evidence, and the required successor record; no new threshold is adopted without approval.

**Record.** File the evaluation evidence and the owner's freeze/retrain decision. If retraining is approved, record the resulting artifact and valid evaluation in the existing model-governance records. Offer an ADR or ADR-027 successor only if the specific selected approach passes all three ADR-threshold tests in §2; do not pre-commit to new gate keys or thresholds.

### R-07 · Feature data-quality audit

**Evidence from the EDA files.**

- 24 features have maxima at or above 1e6; several reach 1e9–1e10 while their lower quantiles remain near zero (for example Quick Ratio max 9.23e9; Current Ratio max 2.75e9). This establishes extreme values, not their cause; sentinel/encoding/overflow provenance is unverified.
- `Net Income Flag` is constant (1.0 on all 6,819 rows). `Liability-Assets Flag` is positive on about 0.12% of rows.
- The top-importance features are near-constant. Interest Expense Ratio has an IQR of about 5e-4; the three interest-rate columns and DFL have IQRs near 1e-4, with skewness down to about −53 and kurtosis up to about 3,100. The boxplots render as flat lines for both classes, so the signal sits in fourth-decimal differences or a few tail rows.
- The IQR outlier rule is uninformative on such features (DFL shows 22% "outliers" because its IQR is tiny). The headline of 71 of 95 features above 5% outliers, and the D-1.12 premise that tails are the risk signal, need re-characterization. **Owner correction recorded (2026-10-20):** the D-1.12 / ADR-026 decision to refrain from IQR-based removal or unverified winsorization survives because IQR-based removal is the wrong tool either way, but the rationale must be restated in the R-07 audit report from *"tails are the risk signal"* to *"no removal without provenance"* (magnitudes of $10^9\text{--}10^{10}$ on ratios like Quick Ratio look like encoding artifacts rather than tail risk). A superseding ADR is warranted only if the audit outcome passes all three ADR-threshold tests in §2.
- The correlation heatmap selects the top 30 features by raw variance, which may over-represent scale-dominated features. The three interest-rate columns have similar moments, and the ROA(A/B/C) family appears in top importance; these are hypotheses to verify with a full correlation analysis, not proof of collinearity. ADR-024 verifies one exact duplicate pair (r=1.0).
- Importance was computed on a random-forest proxy, not the promoted model, and correlated groups split importance.

**Action.**

1. Produce per-feature tail tables by class and inspect suspected extreme-value encodings against authoritative dataset documentation; do not infer a sentinel meaning from magnitude alone.
2. Recompute the full 95×95 Spearman matrix and report high-correlation pairs/clusters, with the known exact duplicate distinguished from approximate correlation.
3. Evaluate permutation importance for the promoted model and correlated groups using a valid evaluation design (coordinate with R-06; do not use the selection-contaminated test set as an unbiased importance estimate).
4. Measure sensitivity to feature perturbations with an explicit scale-aware protocol; report PD/rating changes, but do not use arbitrary noise levels as a production precision requirement.
5. Present options for constant-feature handling and extreme-value treatment. Do not drop, cap, or remove rows without a human decision and evidence; preserve ADR-026 unless explicitly superseded, and restate the D-1.12 rationale in the audit report as *"no removal without provenance."*
6. **Yeo-Johnson power-transform check (check, not a pre-assumed finding):** inspect the fitted `PowerTransformer(method="yeo-johnson", standardize=True)` $\lambda$ parameters (`lambdas_`) and post-transform quantile ranges (`min`, `p01`, `p25`, `p50`, `p75`, `p99`, `max`, IQR) for the 24 columns with maxima $\ge 10^6$, verifying whether fitting across a $10^{10}$ spread compresses the $[0, 1]$ bulk where most observations sit or introduces numerical instability.

**Done when.** Audit report filed and feature-policy decisions recorded. Any feature change requires an approved contract/version impact assessment and, if it changes model inputs, an authorized retrain and successor record.

**Record.** File the audit and approved feature policy with the model/evaluation evidence. Preserve ADR-026 unless the owner explicitly approves a change; any proposed superseding decision must be assessed against all three ADR-threshold tests in §2 before offering an ADR.

### R-08 · Reproducible DVC lineage for Tier 1

**Finding.** Confirmed: current `dvc.yaml` has only `validate` and `stub_train`; it has no `params:` dependencies and no trained model, evaluation metrics, plots, or promotion output. The actual training/export commands exist separately from DVC. Thus the DVC pipeline demonstrates the Phase 0 validation gate but does not reproduce Tier 1 training/promotion. INV-7 still gates the defined training command when invoked; the missing DVC lineage is a reproducibility/governance gap, not evidence that validation is bypassed.

**Action.** Propose a DVC stage design that traces the approved training/evaluation workflow and its configuration, with explicit metrics/artifact dependencies and promotion-gate failure behavior. Keep the existing pipeline until the plan is approved; preserve MLflow's accepted tracking role and account for the configured local-only remote when defining clean-clone reproducibility.

**Done when.** An approved pipeline reproduces the documented training and promotion evidence from a clean environment, or the owner explicitly accepts a documented exception. Test that invalid data stops before training and a gate-failing candidate cannot be promoted.

**Record.** File the Phase 1 corrective note and approved reproducibility exception or implementation scope. A pipeline-topology choice gets an ADR offer only if it passes all three ADR-threshold tests in §2.

### R-09 · Tier 2 semantics and sensitivity

**Finding.** Tier 2 returns P10/P50/P90 probability-of-default bands, not loss estimates and not a confidence interval for model-estimation uncertainty. The code's current simulation uses `asset_correlation`, `seed`, and iteration count; configured `macro_volatility`, `debt_service_shock_std`, and `asset_haircut_std` are not consumed by `engine.py`. The implementation's three correlated shocks are blended into the Vasicek PD transform, so the intended interpretation and the unused configuration need resolution. The closed-form benchmark validates implementation against its chosen formula, not that formula's empirical realism.

**Action.**

1. Describe the current outputs as simulated PD percentiles under the implemented Vasicek-style assumptions; do not call them loss bands or model-confidence intervals.
2. Decide whether unused volatility/shock parameters should be removed, implemented, or retained for a separately specified future model. Do not publish sensitivity claims for parameters that currently have no effect.
3. Document the provenance and meaning of each effective simulation parameter and add a sensitivity analysis over those parameters.
4. Decide whether a simulation-configuration version belongs in the evidence bundle before adding a contract field.
5. Defer a calibration-uncertainty simulation unless it is separately specified and approved.

**Done when.** Sensitivity report filed; schema docs and rubric text updated.

**Record.** Correct output labels and document measured parameter semantics in the relevant contract/evaluation. Offer an ADR only if an approved behavior change passes all three ADR-threshold tests in §2.

### R-10 · Gateway pricing and usage verification

**Finding.** `params.yaml` records identical provider rates of $0.075 input / $0.30 output per million tokens for both Gemini (`gemini-2.5-flash`) and Groq (`openai/gpt-oss-20b`), dated 2026-10-12. Identical rates across two different providers and model families strongly suggest one rate block was copied onto the other. This review did not verify those rates against current provider-published pricing, whether reasoning tokens are represented in reported usage, or whether each provider's billing unit matches the implementation. Treat current cost estimates as unverified until checked against primary sources, and run this check first in Wave A.

**Impact.** Cost logging is only as accurate as configured rates and trustworthy usage metadata. No conclusion about current per-report cost or ceiling compliance is supported by this review.

**Action.** Verify rates, billing units, and usage-token coverage on each provider's primary pricing/API documentation; update rate and date only from evidence. Add a deterministic cost fixture based on verified rates. Any staleness warning or per-persona token budget is a separate proposal, not an assumed requirement. Phase 3 is closed; changes to its accepted behavior require change management.

**Done when.** Verified source and calculation evidence are recorded; any config/test change is approved and validated.

### P2 items

### R-11 · Tooling and dependency preparation

- `pyproject.toml` currently has no Tier 3/agent dependency group; keep any additions out of the lean serving dependencies, consistent with ADR-010/022.
- Async test support and strict `live`/`slow` markers are not configured; add only what the approved orchestration and tests need.
- Ruff enables E/W/F/I/UP; Pyright is in `basic` mode. Consider additional rules/type-checking only after recording current baseline and assessing the expected maintenance cost.
- Development dependencies include `httpx2` while runtime code uses `httpx`; verify which tests import/use it and whether it tests production behavior before changing dependencies. Do not change transport on this evidence alone.
- `lightgbm>=4.7.0` has no upper bound, unlike other model dependencies; decide whether a bound is needed based on tested compatibility.

**Done when.** A bounded tooling proposal is approved, baseline and compatibility evidence are recorded, and CI remains green. These are not Phase 4 prerequisites unless the approved implementation plan requires them.

### R-12 · Documentation drift sweep

- `system_design.md` §6 introduction says implementing code does not exist, despite completed Phase 1–3 implementation and ADR-034.
- README's ADR ledger/tree references should be reconciled with current ADR-034 and `reports/docs/phases/phase_3/` structure.
- `scoping_doc.md` retains a late-September target and says ADR-001 through ADR-016 are pending; both are stale relative to Phase 3 closure and the accepted ledger.
- `params.yaml` simulation settings lack nearby ADR references for the implemented simulation/extraction behavior; add references only if the project retains the code-link convention for configuration.
- Other routing-file typo/duplication cleanup is unrelated to the Phase 4 gate; keep it out of this remediation unless separately requested.

### R-13 · Phase 3 residual operational checks

- The four suite skips are named and explained: three container integration tests skip without Docker; one provider smoke test is opt-in. No PIR addendum is needed for those known skips.
- Phase 3 has deterministic mocked fallback tests, captured-event/redaction tests, and recorded live provider qualification. No live forced-outage drill was evidenced; decide whether that is needed for this portfolio system before any provider call.
- The configured user-agent is part of the approved Phase 3 gateway contract. Do not change it based on speculation about provider terms or a presumed WAF issue; reopen only with evidence and change management.
- Before relying on live providers in Phase 4, verify the lifecycle/deprecation status of both pinned models from primary sources. A `model_review_date` config field is optional pending an operational decision.

### R-14 · Reviewer reproducibility

- `.dvc/config` points to `../../acras_dvc_remote`, a local path outside the repository; a clean clone without that sibling remote cannot retrieve the tracked data via `dvc pull`.
- The dataset is DVC-tracked and ADR-011 records its expected dimensions and checksums; document a supported clean-clone acquisition/verification path without changing the approved local-remote design by implication.
- README's `.env.example` reference matches the repository filename. Its copy command is Unix-style; add and verify a Windows PowerShell quickstart if Windows reproduction is in the supported scope.

**Done when.** A clean-environment walkthrough retrieves/verifies the pinned dataset and reaches a served PD, or the owner records the intended limitation. Do not inspect or expose local `.env` contents.

### R-15 · Non-mutating Great Expectations suite tests

**Finding.** Running `uv run pytest` dirty-mutates the tracked file `gx/expectations/bankruptcy_data_suite.json` with 46 newly generated expectation UUIDs. Root cause verified in `src/pipelines/data_contracts.py`: `build_bankruptcy_suite(context=None)` defaults to `gx.get_context(mode="file")`, builds a fresh `gx.ExpectationSuite(name=SUITE_NAME)`, and calls `context.suites.add_or_update(suite)` on line 225. Whenever `tests/unit/test_data_contracts.py::test_build_bankruptcy_suite` (or a fallback path in `validate_dataset`) runs without an ephemeral context, it overwrites the committed JSON suite on disk. Tests that mutate tracked repository artifacts create diff noise and undermine the clean-clone reproducibility claims in R-08 and R-14.

**Action.** Separate in-memory/ephemeral suite construction (`gx.get_context(mode="ephemeral")` or `persist: bool = False` by default) from explicit CLI persistence (`--save-suite-only`), or pass an ephemeral context in unit tests while loading the persisted suite read-only during `validate_dataset`.

**Done when.** Full `uv run pytest` leaves `git status --porcelain` completely clean and preserves the SHA-256 digest of `gx/expectations/bankruptcy_data_suite.json`.

## 5. Execution sequence and Wave A work order

**Wave A · Establish evidence and close fast hygiene (hard time-box: 6.0 hours total / 1 working day).** Execute `W-A1` through `W-A8` in priority order below. Output: reproducible evidence tables/artifacts, the R-15 non-mutating test fix, and bounded options; no model freeze/retrain, feature change, or provider-config change is authorized by measurement alone.

### 5.1 Wave A work order (tasks, time-boxes, and falsification checks)

| Order / ID | Item & scope | Time-box | Deliverable / evidence output | Falsification check | Blocks Tier 3 entry? |
| --- | --- | --- | --- | --- | --- |
| **W-A1** (R-10, R-13) | **Provider pricing, token-billing & lifecycle check (run first).** Verify primary-source pricing, reasoning-token billing rules, and deprecation/lifecycle dates for `gemini-2.5-flash` (Google AI Studio) and `openai/gpt-oss-20b` (Groq). Resolve the suspect identical `$0.075` / `$0.30` per-1M rates in `params.yaml`. | **30 min** | Source table with URLs, effective dates, input/output/reasoning token rates, model lifecycle status, and exact diff proposed for `params.yaml` + deterministic cost fixture. | Verify a synthetic usage payload with non-zero reasoning/completion tokens against each provider's published billing formula; fail if Gemini and Groq rates remain unverified duplicates or if calculated cost deviates by $> 10^{-6}$ USD. | **Yes** (cost/lifecycle prerequisite before live Tier 3 calls) |
| **W-A2** (FR3, R-01, D-10) | **FR3 / CRO field reconciliation & `EvidenceBundle` v2 contract table.** Specify the proposed PD-denominated replacement for `tail_loss_estimate` (e.g., `p90_pd` / `pd_band.p90`) and complete the `EvidenceBundle` v2 field/provenance table (`observed` vs `derived` vs `synthetic`) so 3–5 seed cases can be authored directly as `EvidenceBundle` fixtures under INV-2. | **45 min** | Field-by-field contract table + PRD FR3 / `tier3_persona_architecture.md` change-note ready for owner sign-off. | Schema validation test rejects any `EvidenceBundle` fixture with missing provenance tags, non-finite ratios, all-zero `financial_ratios`, or ungrounded loss claims when LGD/EAD are absent. | **Yes (real Phase 4 blocker)** |
| **W-A3** (R-15) | **Fix GX test-suite mutation of tracked expectation IDs.** Decouple `build_bankruptcy_suite()` / `test_build_bankruptcy_suite` from `gx.get_context(mode="file")` overwrite so `pytest` never rewrites `gx/expectations/bankruptcy_data_suite.json` unless `--save-suite-only` is invoked. | **30 min** | Minimal patch in `src/pipelines/data_contracts.py` (and/or `tests/unit/test_data_contracts.py`) + regression test asserting file digest invariance. | Record SHA-256 of `gx/expectations/bankruptcy_data_suite.json` before and after `uv run pytest`; test fails if digest changes or `git status --porcelain` is non-empty. Temporarily forcing `mode="file"` overwrite must trip the assertion. | **Yes** (repo hygiene before Wave A/B commits) |
| **W-A4** (R-05) | **Gateway structured-output qualification.** Run a bounded probe ($N = 5$ calls per provider via the Phase 3 gateway) enforcing `PersonaVerdict` JSON schema on `gemini-2.5-flash` and `openai/gpt-oss-20b`. | **45 min** | Recorded schema-valid rate, p50/p95 latency, token usage (including any hidden reasoning tokens), and decision evidence for D-05 (gateway-direct vs adapter). | Inject a deliberately malformed / truncated JSON response and a wrong-enum recommendation (`"decline"`) through mock transport to prove `PersonaVerdict` validation fails loudly and triggers at most one bounded repair attempt. | **Yes** (locks D-05 / Tier 3 node boundary) |
| **W-A5** (R-06) | **Tier 1 promotion-gate calibration sensitivity & selection-leakage audit.** (a) Apply monotone logit-shift $p'(\delta) = \sigma(\operatorname{logit}(p) + \delta)$ and logit-scale $p'(\gamma) = \sigma(\gamma \cdot \operatorname{logit}(p))$ distortions to the promoted model's probabilities; record exact $(\delta^*, \gamma^*)$, mean-PD shift, and ECE where `brier_threshold: 0.030` first trips while ROC-AUC stays constant. (b) Quantify 5-fold CV vs test-set ranking optimism across the 12 candidates. | **75 min** | Audit section with distortion-trip curve, minimum detectable miscalibration $(\delta^*, \gamma^*)$, 12-candidate CV vs test rank table, and retain-vs-retrain options. | Confirm ROC-AUC is invariant ($\Delta \text{AUC} = 0$) across strictly increasing $\delta > 0$ shifts while Brier monotonically degrades above `0.030`; confirm $\delta = 0$ reproduces the exact ADR-027 test Brier (`0.0209`). | **No for decoupled Tier 3** (blocks end-to-end demo / model freeze sign-off) |
| **W-A6** (R-07) | **Feature quality & Yeo-Johnson $\lambda$ / range audit.** (a) Inspect fitted `PowerTransformer` $\lambda$ (`lambdas_`) and post-transform quantile ranges (`min`, `p01`, `p50`, `p99`, `max`, IQR) on the 24 columns with maxima $\ge 10^6$. (b) Compute 95×95 Spearman clusters, class-conditional tails, and restate D-1.12 rationale as *"no removal without provenance."* | **75 min** | R-07 audit report with 24-column Yeo-Johnson table, Spearman cluster table, and D-1.12 rationale correction. | Compare pre- and post-transform rank order and `[0, 1]` bulk IQR on the 24 columns; flag any column where post-transform IQR on the `[0, 1]` bulk collapses below $10^{-6}$ or produces non-finite values. | **No for decoupled Tier 3** (blocks only if audit forces retrain) |
| **W-A7** (R-01, R-09) | **Dataset-to-ratio trace & Tier 2 parameter sensitivity.** (a) Document the exact mismatch between the 94 dataset features and `compute_financial_ratios` aliases. (b) Verify unused `params.yaml` shock keys (`macro_volatility`, `debt_service_shock_std`, `asset_haircut_std`) have zero effect and sweep active `asset_correlation` $\in [0.05, 0.30]$. | **30 min** | Sensitivity table + deterministic ratio-validation rule rejecting all-zero/missing source keys. | Perturb unused shock parameters by $10\times$ and confirm `PDBand` output changes by `0.0` (proving dead config); feed a raw CSV row into updated ratio validator and confirm it raises `ValueError` rather than emitting seven `0.0` ratios. | **No for decoupled Tier 3** (blocks raw-row → Tier 2 → Tier 3 pipeline) |
| **W-A8** (R-08, R-14) | **DVC lineage design & clean-clone reproducibility check.** Draft the proposed `dvc.yaml` stage graph (`validate` → `train` → `evaluate_gate`) and document clean-clone dataset verification against ADR-011 checksums. | **30 min** | Proposed `dvc.yaml` topology + Phase 1 corrective note / reproducibility walkthrough. | Dry-run graph check confirms `train` depends on `data/raw/data.csv`, `params.yaml`, and gate signal, and that a failing promotion gate exits non-zero before writing promoted artifacts. | **No for decoupled Tier 3** (governance/reproducibility hygiene) |

**Wave B · Resolve evidence-gated items.** Return with bounded results from Wave A (`W-A1`–`W-A8`), close the FR3 / `tail_loss_estimate` → `p90_pd` decision first, and lock the `EvidenceBundle` v2 seed-case contract. D-01–D-11 are already approved; request a new owner decision only where Wave A evidence requires selecting a threshold, formula, or freeze/retrain branch.

**Wave C · Prepare after approval.** Obtain separate approval for the Phase 4 candidate scope/specification and implementation plan. Author the 3–5 seed cases as validated `EvidenceBundle` fixtures so Tier 3 work can proceed decoupled from upstream Tier 1 retraining or raw-row ratio mapping if desired.

**Critical path into Phase 4 (decoupled via `EvidenceBundle` seed fixtures):** `W-A1` (pricing/lifecycle) + `W-A2` (FR3 / `p90_pd` + `EvidenceBundle` v2 contract) + `W-A3` (GX test fix) + `W-A4` (gateway structured-output probe) → close Tier 3 contracts (R-02/R-03/R-05) and 3–5 `EvidenceBundle` seed cases (R-04) → approve Phase 4 plan (**2.5 hours of Wave A work on the critical path**). `W-A5`–`W-A8` run in the remaining 3.5 hours of the Wave A time-box and gate the end-to-end raw-row demo path and model-governance record, not Tier 3 graph development.

## 6. Phase 4 planning entry gate (decoupled Tier 3 gate vs end-to-end demo gate)

**Status 2026-10-20:** D-01–D-11 are approved (§7, §9) and all 8 gate items below remain unchecked. Because Tier 3's input contract under INV-2 is `EvidenceBundle`, authoring the 3–5 seed cases as validated `EvidenceBundle` fixtures decouples Phase 4 Tier 3 implementation from upstream Tier 1 retraining and raw-CSV ratio extraction. The 8 gate items are therefore grouped into **Gate R-A (hard prerequisites before Phase 4 Tier 3 planning/code)** and **Gate R-B (prerequisites before end-to-end raw-row demo & Phase 5 promotion)**.

### Gate R-A · Hard prerequisites before Phase 4 Tier 3 planning
- [ ] PRD FR3's loss-band wording is reconciled with the implemented PD-percentile output (`tail_loss_estimate` replaced with a PD-denominated field such as `p90_pd` / `pd_band.p90`); reports do not imply loss values without defined LGD/EAD inputs and calculations.
- [ ] The Tier 3 input (`EvidenceBundle` v2 with provenance markers), verdict, divergence, escalation, grounding, and failure contracts are resolved or explicitly deferred with bounded implications, and D-02's removal of duplicate analyst nodes is reflected in the architecture docs.
- [ ] Seed-set scope (3–5 `EvidenceBundle` cases) and metrics are approved; offline regression harness can exercise recorded verdicts.
- [ ] Required decisions are recorded; the owner separately approves whether Phase 4 planning may begin.

### Gate R-B · Upstream prerequisites for end-to-end raw-row demo & model-governance closure (non-blocking for decoupled Tier 3 build)
- [ ] Dataset-to-Tier-2 derived-ratio behavior has an approved correction/contract; unsupported fields cannot silently become zero.
- [ ] Tier 1 selection-on-test-set limitation and promotion-gate calibration sensitivity are disclosed and the owner records whether to retain or retrain.
- [ ] The current Tier 2 output meaning and unused simulation settings are documented or addressed by an approved change.
- [ ] Any DVC/reproducibility exception, non-mutating GX test behavior (R-15), and provider operational assumptions (R-10/R-13) are explicitly recorded.

## 7. Owner approvals (recorded)

All choices below were approved by the owner on 2026-10-20. The recommended go-to and rationale text are unchanged; rejected alternatives remain in §4 for traceability. Items marked **evidence first** still return with a short test result before the dependent action; approval of this table does not authorize implementation.

| ID | Owner choice | Recommended go-to (**approved**) | Why this decision matters | Status |
| --- | --- | --- | --- | --- |
| D-01 | Select the Phase 4 input/demo contract: benchmark-feature path, structured financial/deal profile, or a justified deterministic mapping. | Keep benchmark features and profile/deal facts distinct; mark synthetic values and validate all required calculation inputs. | Prevents the Tier 2 zero-ratio path and unsupported evidence from reaching personas. | **APPROVED 2026-10-20** |
| D-02 | Confirm whether any analyst node has a distinct non-duplicative responsibility. | Remove redundant calculation steps; retain only a named deterministic assembly/validation responsibility. | Determines the Tier 3 graph boundary without moving deterministic authority to an LLM. | **APPROVED 2026-10-20** |
| D-03 | Finalize divergence formula, thresholds, and calibration of persona-confidence semantics; INV-4 already fixes the structured field set. | Use canonical labels and deterministic divergence over recommendation, lean, and confidence as INV-4 requires; hold confidence weighting and thresholds until cases support them. Keep persona confidence distinct from Tier 1 confidence. | Implements required escalation consistently and avoids arbitrary confidence semantics. | **APPROVED 2026-10-20** |
| D-04 | Approve the Phase 4 seed-set size and falsifiable exit evidence. | 3–5 smoke cases; pair divergence detection with false-escalation reporting and do not claim statistical performance. | Makes the qualitative exit criterion testable without overclaiming a tiny set. | **APPROVED 2026-10-20** |
| D-05 | After provider qualification, choose gateway-direct LangGraph or a gateway-backed Pydantic AI adapter if both remain viable. | Gateway-direct unless the configured gateway fails the structured-output test or the adapter demonstrates a material benefit. | Fixes the integration boundary and dependency/cost footprint. | **APPROVED 2026-10-20** |
| D-06 | Decide whether a fallback-served verdict near the escalation threshold forces HITL; decide any qualitative-grounding control only after its evidence test. | Deterministic numeric grounding; incomplete/invalid persona results are surfaced for human review. | Defines safe report behavior without letting an LLM judge compute divergence. | **APPROVED 2026-10-20** |
| D-07 | After evaluation, retain the frozen Tier 1 artifact with caveat or authorize retraining under independent final evaluation. | No retraining or gate change before selection-effect evidence and explicit approval. | The current reported test result is not an independent estimate after candidate selection. | **APPROVED 2026-10-20** |
| D-08 | Consider any exception to ADR-026 only after feature-provenance and impact evidence. | Preserve current no-removal/no-winsorization policy. | Protects current accepted feature behavior from unsupported changes. | **APPROVED 2026-10-20** |
| D-09 | Set the required DVC/clean-environment reproducibility scope; separately approve any remote/setup change. | Demonstrate an end-to-end lineage design; do not silently replace the accepted local remote. | Establishes whether reproducibility work blocks Phase 4 and avoids infrastructure scope creep. | **APPROVED 2026-10-20** |
| D-10 | After parameter sensitivity evidence, decide whether unused Tier 2 shock settings should alter engine behavior. | Correctly label existing PD percentiles now; do not activate parameters without evidence and approval. | Changing shock semantics can change deterministic outputs and their interpretation. | **APPROVED 2026-10-20** |
| D-11 | Approve operational/tooling work only where pricing, model lifecycle, reproducibility, or test evidence shows a Phase 4 dependency. | Defer broad hygiene; verify external facts before changing configuration. | Keeps remediation proportional to Phase 4 needs and avoids speculative work. | **APPROVED 2026-10-20** |

**Record-only outcomes (no owner selection needed):** do not silently substitute zero for missing required inputs; do not call PD percentiles losses or confidence intervals; keep all LLM calls behind the gateway; preserve deterministic divergence and uniform low temperature; surface incomplete persona analysis for human review; preserve ADR-026 unless a change is explicitly approved.

**Affirmed 2026-10-20:** the record-only outcomes above were affirmed together with the decision approval; they remain binding constraints, not new choices.

## 8. Open inputs that would sharpen this plan

Remaining inputs are the evidence-first returns under §4, PRD FR3 reconciliation, and primary-source verification of provider pricing, usage-token billing, and model lifecycle; owner decisions are recorded in §7 and §9. The raw data, ADR-027, source code, DVC configuration, invariants, Tier 3 architecture, capability-profile gates, PRD, and Phase 3 evidence have been reviewed.

## 9. Owner decision record

**Approver:** Sebastián Garrido Arévalo · **Date:** 2026-10-20 · **Decision:** approve D-01 through D-11.

**Effect.** Fixes each recommended go-to and its stated sequencing. Does not authorize implementation or Phase 4 planning; Phase 4 still requires separate planning and approval. Alternatives, rejected options, and trade-off text are retained unedited for traceability.

| ID | Approved outcome | Remaining condition before acting |
| --- | --- | --- |
| D-01 | Benchmark features and profile/deal facts kept distinct; synthetic values marked; unsupported calculations rejected, never zero-filled. | Approved field table and required-input tests. |
| D-02 | Duplicate rating/ratio steps removed; only a named deterministic assembly/validation node may remain. | Consistent architecture/data-flow text and graph contract test. |
| D-03 | Canonical labels; deterministic divergence over recommendation, lean, and persona confidence; persona confidence distinct from Tier 1 confidence. | Anchored lean rubric, confidence semantics/weighting, formula, escalation truth table, and case evidence before fixing thresholds/weights. |
| D-04 | 3–5-case smoke set; divergence detection reported with false-escalation/convergence; no statistical claim. | Versioned cases with labels/rationale and offline harness. |
| D-05 | Gateway-direct LangGraph with Pydantic validation preferred. | Bounded gateway structured-output qualification; adapter only if it shows material benefit. |
| D-06 | Deterministic numeric grounding; incomplete/invalid persona results surfaced for human review. | Qualitative-grounding evidence; explicit policy for fallback-near-threshold HITL. |
| D-07 | No retraining or gate change before selection-effect evidence and explicit approval. | Quantified selection effect and recorded freeze/retrain decision. |
| D-08 | Preserve ADR-026 no-removal/no-winsorization policy. | Any exception requires provenance/impact evidence and owner approval. |
| D-09 | End-to-end DVC lineage design demonstrated; accepted local remote unchanged. | Clean-environment evidence; separate approval for any remote/setup or scope change. |
| D-10 | Current outputs labeled simulated PD percentiles; unused shock parameters not activated. | Parameter-usage/sensitivity evidence and separate approval for behavior change. |
| D-11 | Operational/tooling work limited to demonstrated Phase 4 dependencies. | Primary-source verification of pricing, usage billing, and model lifecycle. |
