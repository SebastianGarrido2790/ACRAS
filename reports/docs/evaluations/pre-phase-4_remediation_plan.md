# Pre-Phase-4 Remediation Plan — ACRAS

*Prepared for Sebastián Garrido Arévalo · 2026-10-19 · Draft v0.2 · Recommendations only; nothing below is authorized until recorded as a human decision.*

## 1. Purpose, scope and limits

This draft consolidates findings from the reviewed requirements, architecture and phase documents, source code, configuration, tests, EDA outputs, and the checked-in raw dataset into a prioritized sequence for consideration before Phase 4 planning. It is a recommendation only: all product, architecture, scope, and threshold decisions remain with the project owner, and Phase 4 planning remains a separate approval.

**Evidence reviewed.** `data/raw/data.csv` has 6,819 rows, one target plus 95 features, 220 positive labels, and no blank fields. The 94-feature canonical Tier 1 schema, training/selection code, promotion gate, Tier 2 ratio extraction and simulation, EvidenceBundle v1, gateway, ADR-027, project invariants, Tier 3 architecture, PRD, roadmap, capability-profile gates, and Phase 3 closure evidence were inspected. The full automated suite reports 191 passed and 4 skipped; the skips are three Docker-daemon-dependent integration cases and one opt-in live-provider smoke test. A source-level local run confirmed that passing a dataset row to the current Tier 2 ratio extractor yields seven zero ratios. Claims below distinguish verified repository facts from proposals and external facts that remain to be checked. No external pricing or provider-lifecycle lookup was performed.

**Primary evidence trail.** [Raw dataset](../../../data/raw/data.csv), [feature schema](../../../src/schemas/features.py), [training/selection code](../../../src/pipelines/training/train.py), [promotion gate](../../../src/pipelines/training/promotion_gate.py), [Tier 2 service](../../../src/tier2_simulation/service.py), [ratio extraction](../../../src/tier2_simulation/ratios.py), [simulation engine](../../../src/tier2_simulation/engine.py), [EvidenceBundle](../../../src/schemas/evidence_bundle.py), [DVC pipeline](../../../dvc.yaml), [parameters](../../../params.yaml), [system design and ADRs](../architecture/system_design.md), [Tier 3 persona architecture](../architecture/tier3_persona_architecture.md), [PRD](../groundedness/prd.md), [capability-profile gates](capability_profile_gates.md), and [Phase 3 closure evidence](../phases/phase_3/implementation_plan.md).

## 2. Priority and sizing

- **P0:** Phase 4 would be unsound or unfalsifiable without it.
- **P1:** weakens the deterministic core that Tier 3 consumes; may force a Tier 1 retrain.
- **P2:** hygiene that is cheaper to fix before Tier 3 code exists.
- **Sizing:** effort is TBD (to be determined) until the owner selects scope and approach; this draft does not make schedule commitments.

## 3. Register

| ID | Pri | Item | Size | Human decision |
| --- | --- | --- | --- | --- |
| R-01 | P0 | Input contract and derived-field provenance | TBD | Yes |
| R-02 | P0 | Reconcile planned analyst-node responsibilities | TBD | Yes |
| R-03 | P0 | Divergence and escalation specification | TBD | Yes |
| R-04 | P0 | Seed golden set and falsifiable Phase 4 exit | TBD | Yes |
| R-05 | P0 | Orchestration contract and failure semantics | TBD | Yes |
| R-06 | P1 | Tier 1 gate-strength and selection-leakage audit | TBD | Yes |
| R-07 | P1 | Feature data-quality audit | TBD | Yes |
| R-08 | P1 | Add reproducible DVC lineage for Tier 1 | TBD | Yes |
| R-09 | P1 | Tier 2 semantics and sensitivity | TBD | Yes |
| R-10 | P1 | Gateway pricing and usage verification | TBD | Yes, if a change is proposed |
| R-11 | P2 | Tooling and dependency preparation | TBD | Yes, before changes |
| R-12 | P2 | Documentation drift sweep | TBD | Yes, before scope changes |
| R-13 | P2 | Phase 3 residual operational checks | TBD | Yes, for live checks/config changes |
| R-14 | P2 | Reviewer reproducibility | TBD | Yes, before changing remote/setup |

## 4. P0 items

### R-01 · Input contract and derived-field provenance

**Finding.** Verified: the dataset supplies 95 ratio-like features (94 canonical Tier 1 inputs after ADR-024), not financial statement line items, loan terms, sector, or covenant history. The PRD expects synthetic structured company profiles for production/demo input; that is not the same contract as the benchmark dataset row. More urgently, `run_simulation_pipeline` passes `EvidenceBundle.raw_features` directly to `compute_financial_ratios`, whose aliases expect underlying accounting amounts (for example `current_assets` and `current_liabilities`) and silently use zero for missing keys. A raw dataset row therefore currently produces seven all-zero `financial_ratios`. The v1 evidence schema requires a non-empty mapping but does not reject those semantically invalid zeros. The Tier 3 design also lists proposed fields (tail loss, capital consumption, concentration, covenant flags, growth, pipeline) without an implemented source/formula contract. The current engine returns PD bands, not loss bands; no LGD/EAD loss calculation was found.

**Action.**

1. Resolve the input-contract mismatch before choosing a UI/demo path: document the distinction between the model's 94 benchmark features and the PRD's synthetic structured profile. Compare a dataset-row/ratio input path with statement-field inputs and a deterministic, validated mapping; state what each can and cannot establish.
2. Specify every EvidenceBundle v2 field with its source, formula, owner, units, assumptions, validation, and whether the value is observed, synthetic, or derived. Do not call PD percentiles loss estimates; add LGD/EAD or other economics only if the human-approved scope requires them and their inputs are defined.
3. Correct the dataset-row ratio path: either provide compatible source fields and explicit required-input validation, or map/rename the fields only under an approved, documented derivation. Missing source data must not silently become a plausible zero.
4. Define golden/demo-case construction and provenance. Perturbing real rows is one candidate for model-feature coverage, but cannot by itself supply deal terms or qualitative facts; label any synthetic additions and do not treat them as observed data.

**Done when.** The input contract and field table have human approval; tests prove required source inputs, reject unsupported/missing data, and establish deterministic-only lineage for calculation fields (INV-1). Any decision to change an existing interface or model input contract follows change management.

**Record.** ADR-016 (fills the reserved Tier 3 schema-fields slot) plus a `derived_fields` block in params.yaml.

### R-02 · Reconcile planned analyst-node responsibilities

**Finding.** These are planned documentation components, not implemented agents (`src/agents/` contains package skeletons). The architecture's data-flow text assigns rating to a Data Scientist Agent although the serving/Tier 1 path already supplies rating; it assigns ratio computation to a Financial/Domain Analyst Agent although the Tier 2 service already computes ratios. FR5 and ADR-033 require deterministic ratio computation, not an LLM agent. The persona architecture still describes these analyst agents as workers, so the intended component boundary is inconsistent.

**Options.** A: remove redundant analyst-agent steps and have orchestration consume Tier 1/Tier 2 outputs. B: retain named deterministic orchestration nodes if they perform an explicit, non-duplicated contract/assembly responsibility. The existing docs do not establish a need for B.

**Done when.** The human-approved component boundary is consistent in the Tier 3 architecture and system data flow; a graph/contract test confirms that only the three persona nodes make LLM calls and that all calculations remain deterministic.

**Record.** Record a new ADR only if the owner makes a material architecture decision; no agent retirement is authorized by this draft.

### R-03 · Divergence and escalation specification

**Finding.** The deterministic divergence function is specified but not implemented. The structured `PersonaVerdict` model exists, but it has no anchored `lean` rubric; `confidence` is persona-reported, while the separate "Tier 1 confidence" required by FR8/INV-9 has no definition. There is also a contract mismatch: the implemented Pydantic schema uses `reject`, while the persona-architecture example says `decline`; the PRD uses `reject`. The threshold remains provisional.

**Action.**

1. Define persona-specific `lean` anchors and examples; align the recommendation vocabulary to the existing canonical `approve` / `conditional` / `reject` contract unless the owner approves a versioned change.
2. Implement and document the deterministic formula over structured fields, including categorical mismatch, lean spread, weights, and the role of confidence (or its removal through an approved schema decision).
3. Define Tier 1 confidence as a deterministic function of Tier 1/2 outputs only. Candidate proxies include distance to a rating threshold and relative PD-band width; decide whether either is valid before selecting and calibrating a threshold. Do not use persona-reported confidence as a substitute.
4. Write the escalation truth table: divergence above threshold, low Tier 1 confidence, any persona failure, schema-invalid output, fallback-served verdict (see R-05).

**Done when.** Pure functions have unit and property tests (invariant under persona permutation; monotonic in lean spread); every truth-table row is tested.

**Record.** ADR for divergence and escalation; PRD FR7/FR8 clarified through change-management.

### R-04 · Seed golden set and falsifiable Phase 4 exit

**Finding.** The roadmap's Phase 4 exit criterion ("genuinely different verdicts") is qualitative, while the fuller golden-set evaluation is scheduled for Phase 5. The PRD/capability-profile documentation already proposes a 20–40-case set and a 3–5-case Phase 4 seed set; the roadmap does not include the seed set. A divergence-recall-only metric would reward always-escalate behavior, so it needs a converge/false-escalation countermetric. Rubrics and labels authored by one person also limit independence. Hosted-model repeatability cannot be guaranteed by temperature alone.

**Action.**

1. Decide whether to adopt the existing 3–5-case Phase 4 seed-set proposal, or the larger 12-case proposal in this draft; neither is approved. Keep either seed set as a development smoke test, not a statistical claim.
2. Report divergence recall and false-escalation rate on converge cases, with per-case verdicts and the exact escalation rule.
3. Freeze about 30% of cases as hold-out before rubrics are tuned.
4. Consider a bounded repeatability protocol (for example, repeated calls on a subset per provider); report recommendation flip rate and divergence-score variation. This would supplement—not silently replace—the ADR-005 fixed-settings regression.
5. Run every case on the primary and on forced fallback.
6. Use verified model rows only for the features they contain; explicitly label synthetic deal terms and qualitative fields (R-01).
7. Put any approved Phase 4 exit-criterion change in its implementation plan; the roadmap is a sequencing artifact, not the authority for technical detail.

**Done when.** The seed set is versioned with labelled expectation and rationale per case; the harness runs offline from recorded responses and live; baseline numbers are recorded with no threshold claimed until Phase 5.

**Record.** Phase 4 precondition; ADR clarifying the ADR-005 test; scoping §9 divergence target stays provisional.

### R-05 · Orchestration contract and failure semantics

**Finding.** Phase 3 provides a generic gateway and bounded primary/fallback handling, not a `PersonaVerdict` schema-constrained interface. Its no-same-provider-retry policy is explicit; the Tier 3 repair/retry policy is not. The design documents do not settle partial-persona failure, fallback provenance, or whether a fallback verdict changes HITL behavior. Gemini and Groq use different models, so semantic equivalence is not guaranteed (Phase 3 explicitly disclaims it). The PRD/capability design proposes LLM-as-judge grounding, while deterministic numeric validation is another viable control; INV-4 prohibits LLM judging for divergence, not generally for grounding. Treat the grounding mechanism and its role as an open design decision, not an invariant violation.

**Action.**

1. Test each provider's actual structured-output support through the gateway with a bounded, documented sample; record schema-valid rate, latency, and provider-reported usage. Do not assume a provider's feature works through the configured endpoint.
2. Integration decision. A (recommended): LangGraph nodes call the gateway directly and validate with Pydantic v2; no Pydantic AI in the Tier 3 path. B: Pydantic AI with a gateway-backed model adapter.
3. Failure table. Persona failure: no report; escalate as incomplete (never average two personas). Schema-invalid: at most one bounded repair re-ask through the gateway, counted against the call budget, then fail. Fallback-served: verdict tagged with provider; decide whether a fallback verdict near the threshold forces HITL.
4. Decide the grounding control: compare deterministic validation of report numbers against bundle fields with the existing LLM-judge proposal, including false positives/negatives and whether either blocks a report. Keep report numbers template-bound where feasible.

**Done when.** Provider capability evidence and an approved failure/grounding contract are recorded; failure rows are tested with mock transport, and the selected grounding check has falsification tests.

**Record.** ADR for the Tier 3 orchestration contract.

## 5. P1 items

### R-06 · Tier 1 gate-strength and selection-leakage audit

**Finding.**

- `brier_threshold: 0.030` is close to the no-skill baseline: with a 3.23% base rate (220/6,819), predicting the base rate gives a Brier of about 0.0312, so the gate demands only about 3.9% skill.
- The test split holds about 44 positives, so Brier and reliability estimates are noisy.
- `train_and_evaluate_all_models` evaluates all 12 candidates on the held-out test set and sorts them by test Brier score; ADR-027 reports the winning candidate's test metrics. The test set therefore participated in model selection and is not an independent final evaluation set for the selected winner.
- Isotonic calibration on about 176 training positives can be step-shaped and unstable.
- The gate applies a Brier threshold plus an AUC threshold. Training code computes calibration-curve diagnostics, but there is no separate reliability-curve acceptance criterion; clarify whether INV-3/ADR-003's wording intends one.

**Action.** First quantify the selection effect and document the validity limit of the reported test metrics. Then present a human decision on whether to retain the frozen artifact with that caveat or retrain under a corrected evaluation protocol. If retraining is authorized:

1. Select candidates using training-only cross-validation (nested CV if using the same data to tune and estimate generalization); reserve a test set that is consulted once after selection.
2. Report Brier, Brier skill score against the training base rate, AUC/KS, reliability curve and uncertainty intervals; quantify calibration uncertainty given the small positive count.
3. Compare Platt and isotonic calibration inside the selection procedure, not by choosing from final-test outcomes.
4. Update the promotion gate only after measured baselines and human approval; keep Brier and discrimination checks and decide explicitly whether a reliability criterion is also required.

**Done when.** The selection leakage is disclosed in an evaluation report and the owner records a freeze/retrain decision. Any replacement model has a valid final evaluation, promotion evidence, and the required successor record; no new threshold is adopted without approval.

**Record.** ADR amending `promotion_gate` (new params.yaml keys); an ADR-027 successor if retrained.

### R-07 · Feature data-quality audit

**Evidence from the EDA files.**

- 24 features have maxima at or above 1e6; several reach 1e9–1e10 while their lower quantiles remain near zero (for example Quick Ratio max 9.23e9; Current Ratio max 2.75e9). This establishes extreme values, not their cause; sentinel/encoding/overflow provenance is unverified.
- `Net Income Flag` is constant (1.0 on all 6,819 rows). `Liability-Assets Flag` is positive on about 0.12% of rows.
- The top-importance features are near-constant. Interest Expense Ratio has an IQR of about 5e-4; the three interest-rate columns and DFL have IQRs near 1e-4, with skewness down to about −53 and kurtosis up to about 3,100. The boxplots render as flat lines for both classes, so the signal sits in fourth-decimal differences or a few tail rows.
- The IQR outlier rule is uninformative on such features (DFL shows 22% "outliers" because its IQR is tiny). The headline of 71 of 95 features above 5% outliers, and the D-1.12 premise that tails are the risk signal, need re-characterization.
- The correlation heatmap selects the top 30 features by raw variance, which may over-represent scale-dominated features. The three interest-rate columns have similar moments, and the ROA(A/B/C) family appears in top importance; these are hypotheses to verify with a full correlation analysis, not proof of collinearity. ADR-024 verifies one exact duplicate pair (r=1.0).
- Importance was computed on a random-forest proxy, not the promoted model, and correlated groups split importance.

**Action.**

1. Produce per-feature tail tables by class and inspect suspected extreme-value encodings against authoritative dataset documentation; do not infer a sentinel meaning from magnitude alone.
2. Recompute the full 95×95 Spearman matrix and report high-correlation pairs/clusters, with the known exact duplicate distinguished from approximate correlation.
3. Evaluate permutation importance for the promoted model and correlated groups using a valid evaluation design (coordinate with R-06; do not use the selection-contaminated test set as an unbiased importance estimate).
4. Measure sensitivity to feature perturbations with an explicit scale-aware protocol; report PD/rating changes, but do not use arbitrary noise levels as a production precision requirement.
5. Present options for constant-feature handling and extreme-value treatment. Do not drop, cap, or remove rows without a human decision and evidence; preserve ADR-026 unless explicitly superseded.

**Done when.** Audit report filed and feature-policy decisions recorded. Any feature change requires an approved contract/version impact assessment and, if it changes model inputs, an authorized retrain and successor record.

**Record.** ADR (extends ADR-024; may supersede ADR-026).

### R-08 · Reproducible DVC lineage for Tier 1

**Finding.** Confirmed: current `dvc.yaml` has only `validate` and `stub_train`; it has no `params:` dependencies and no trained model, evaluation metrics, plots, or promotion output. The actual training/export commands exist separately from DVC. Thus the DVC pipeline demonstrates the Phase 0 validation gate but does not reproduce Tier 1 training/promotion. INV-7 still gates the defined training command when invoked; the missing DVC lineage is a reproducibility/governance gap, not evidence that validation is bypassed.

**Action.** Propose a DVC stage design that traces the approved training/evaluation workflow and its configuration, with explicit metrics/artifact dependencies and promotion-gate failure behavior. Keep the existing pipeline until the plan is approved; preserve MLflow's accepted tracking role and account for the configured local-only remote when defining clean-clone reproducibility.

**Done when.** An approved pipeline reproduces the documented training and promotion evidence from a clean environment, or the owner explicitly accepts a documented exception. Test that invalid data stops before training and a gate-failing candidate cannot be promoted.

**Record.** Phase 1 corrective note; ADR only if pipeline topology changes.

### R-09 · Tier 2 semantics and sensitivity

**Finding.** Tier 2 returns P10/P50/P90 probability-of-default bands, not loss estimates and not a confidence interval for model-estimation uncertainty. The code's current simulation uses `asset_correlation`, `seed`, and iteration count; configured `macro_volatility`, `debt_service_shock_std`, and `asset_haircut_std` are not consumed by `engine.py`. The implementation's three correlated shocks are blended into the Vasicek PD transform, so the intended interpretation and the unused configuration need resolution. The closed-form benchmark validates implementation against its chosen formula, not that formula's empirical realism.

**Action.**

1. Describe the current outputs as simulated PD percentiles under the implemented Vasicek-style assumptions; do not call them loss bands or model-confidence intervals.
2. Decide whether unused volatility/shock parameters should be removed, implemented, or retained for a separately specified future model. Do not publish sensitivity claims for parameters that currently have no effect.
3. Document the provenance and meaning of each effective simulation parameter and add a sensitivity analysis over those parameters.
4. Decide whether a simulation-configuration version belongs in the evidence bundle before adding a contract field.
5. Defer a calibration-uncertainty simulation unless it is separately specified and approved.

**Done when.** Sensitivity report filed; schema docs and rubric text updated.

**Record.** ADR amendment for Tier 2 semantics.

### R-10 · Gateway pricing and usage verification

**Finding.** `params.yaml` records provider rates of $0.075 input / $0.30 output per million tokens for Gemini and Groq, dated 2026-10-12, with source labels. This review did not verify those rates against current provider-published pricing, whether reasoning tokens are represented in reported usage, or whether each provider's billing unit matches the implementation. Treat current cost estimates as unverified until checked against primary sources.

**Impact.** Cost logging is only as accurate as configured rates and trustworthy usage metadata. No conclusion about current per-report cost or ceiling compliance is supported by this review.

**Action.** Verify rates, billing units, and usage-token coverage on each provider's primary pricing/API documentation; update rate and date only from evidence. Add a deterministic cost fixture based on verified rates. Any staleness warning or per-persona token budget is a separate proposal, not an assumed requirement. Phase 3 is closed; changes to its accepted behavior require change management.

**Done when.** Verified source and calculation evidence are recorded; any config/test change is approved and validated.

## 6. P2 items

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

## 7. Execution sequence

**Wave A · Establish evidence (no decisions).** R-01 input-to-ratio trace, R-06 model-selection impact, R-07 feature profile, R-08 DVC lineage design, R-09 simulation parameter usage, R-10 provider pricing/usage verification, and R-13 lifecycle inventory. Output: evidence reports and clearly bounded options; no model freeze/retrain, feature change, or provider-config change is authorized by measurement alone.

**Wave B · Decide.** Present options for the input contract (R-01), component responsibilities (R-02), divergence/escalation contract (R-03), seed set (R-04), orchestration/grounding (R-05), Tier 1 freeze/retrain (R-06), feature handling (R-07), DVC scope (R-08), and Tier 2 parameter semantics (R-09). Record only choices explicitly made by the owner.

**Wave C · Prepare after approval.** Implement only approved decisions; then version the seed set, close required documentation/reproducibility work, and add tooling only where the approved Phase 4 plan requires it.

**Proposed critical path:** R-01 and R-06 evidence → human decisions about contract and Tier 1 validity → R-03/R-05 contracts → R-04 cases → approved Phase 4 plan. Effort estimates are intentionally omitted until scope and decisions are settled; earlier 7–10-day estimates were not supported by task-level sizing.

## 8. Proposed Gate R: owner decision before Phase 4 planning

- [ ] Dataset-to-Tier-2 derived-ratio behavior has an approved correction/contract; unsupported fields cannot silently become zero.
- [ ] Tier 1 selection-on-test-set limitation is disclosed and the owner records whether to retain or retrain.
- [ ] The Tier 3 input, verdict, divergence, escalation, grounding, and failure contracts are resolved or explicitly deferred with bounded implications.
- [ ] Seed-set scope and metrics are approved; offline regression harness can exercise recorded verdicts.
- [ ] The current Tier 2 output meaning and unused simulation settings are documented or addressed by an approved change.
- [ ] Any DVC/reproducibility exception and provider operational assumptions are explicitly recorded.
- [ ] Required decisions are recorded; the owner separately approves whether Phase 4 planning may begin.

## 9. Decisions requested

| ID | Decision | Recommended |
| --- | --- | --- |
| D-R.0 | Treat this as a pre-Phase-4 readiness review, not a new roadmap phase | Yes; consistent with the existing phase sequence |
| D-R.1 | Analyst-node role: remove redundant steps or retain deterministic nodes with distinct responsibility | Lean toward removing duplicate computations; approve an exact role boundary |
| D-R.2 | Phase 4 seed set: 3–5 smoke cases or 12 development cases | 3–5 is the existing capability-profile proposal; 12 is an unvalidated alternative |
| D-R.3 | Tier 1 confidence proxy, or defer confidence-based escalation pending definition | No proxy recommended before evidence |
| D-R.4 | Tier 3 orchestration: gateway-direct LangGraph calls or a gateway-backed Pydantic AI adapter | Gateway-direct is simpler; verify structured-output support first |
| D-R.5 | Tier 2 simulation configuration: resolve unused shock parameters and label PD percentile semantics | Measure/clarify before choosing implementation change |
| D-R.6 | Feature handling for constant/extreme values | Decide only after R-07 evidence; preserve ADR-026 unless explicitly superseded |
| D-R.7 | Tier 1 freeze or retrain and any promotion-gate amendment | Decide after R-06; thresholds from valid evaluation, not invented |
| D-R.8 | Grounding validator policy and whether any live provider failover drill is necessary | Compare deterministic checks and LLM-as-judge; no live drill presumed |
| D-R.9 | DVC lineage and clean-clone data retrieval scope | Decide how much reproducibility must precede Phase 4 |

## 10. Open inputs that would sharpen this plan

Remaining inputs are owner decisions in §9 and primary-source verification of provider pricing, usage-token billing, and model lifecycle. The raw data, ADR-027, source code, DVC configuration, invariants, Tier 3 architecture, capability-profile gates, PRD, and Phase 3 evidence have been reviewed.
