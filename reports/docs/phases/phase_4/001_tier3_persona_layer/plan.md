# Technical Plan — 001 Tier 3 Persona Layer

**Status:** ✅ **APPROVED — 2026-11-02**; clarification gate closed 2026-11-03; Stage 0 complete; Stage 1 complete 2026-11-03 (**Gate 1 passed**, ADR-016 accepted). Stages 2+ not authorized.
**Inputs:** `spec.md` (requirements T3-FR-01…18), `../implementation_plan.md` §6 (D4-01…D4-09), `../../pre-phase_4_remediation/tier3_contracts.md`, `../../architecture/tier3_persona_architecture.md`.
**Constraint:** this plan adds no architectural decision beyond those approved. Where a required detail was left open by an approved decision it is completed here and flagged (§7).

---

## 1. Module layout

```text
src/schemas/evidence_bundle.py        # modify: 4 optional fields; PersonaVerdict.limitations
src/config/loader.py                  # modify: Tier3Config (extra="forbid", frozen=True)
params.yaml                           # modify: tier3: block (provisional)
pyproject.toml                        # modify: [dependency-groups] tier3 + default-groups entry

src/agents/prompts/digest.py          # new: deterministic bundle → persona-visible evidence digest
src/agents/prompts/cro.py             # new: CRO rubric + prompt builder
src/agents/prompts/growth.py          # new: Growth rubric + prompt builder
src/agents/prompts/capital.py         # new: Capital rubric + prompt builder
src/agents/persona_worker.py          # new: one persona invocation (gateway + validation + one repair)

src/agents/orchestration/divergence.py    # new: pure divergence function
src/agents/orchestration/tier1_confidence.py  # new: proxies A and B (pure)
src/agents/orchestration/escalation.py    # new: truth table → Tier3Outcome
src/agents/orchestration/report.py        # new: deterministic report template
src/agents/orchestration/trace.py         # new: Tier3Trace models
src/agents/orchestration/graph.py         # new: LangGraph fan-out → convergence → report

tests/unit/test_contract_fields.py
tests/unit/test_divergence.py
tests/unit/test_tier1_confidence.py
tests/unit/test_escalation.py
tests/unit/test_persona_worker.py
tests/unit/test_tier3_report.py
tests/unit/test_tier3_graph.py
tests/unit/test_offline_harness.py    # extend
```

No new package directory is created: `persona_worker.py` sits in the existing `src/agents/` package, and the deterministic convergence parts sit beside the graph in `src/agents/orchestration/` (whose module docstring already names the convergence node and HITL state machine).

## 2. Evidence contract (P4-01)

**Fields.** Four optional fields on `EvidenceBundle` plus `limitations` on `PersonaVerdict`, exactly as `spec.md` §3. `model_config` stays `extra="forbid", frozen=True`.

**Validator rules (added, narrow):**

1. A field tagged `synthetic` in `provenance` requires a matching `synthetic_assumptions` entry (existing rule, extended from tags to values).
2. A field tagged `derived` is rejected unless it is one of the contract's defined derivations — `financial_ratios` (from `accounting_profile`) and `p90_pd` (from `pd_band.p90`). This closes the current SC-01…SC-04 inconsistency where `revenue_growth_rate`/`concentration_flag` are tagged `derived` with no derivation.
3. No new cross-field requirement beyond the above: an absent value stays `None`, and `None` is not an error for Tier 3 fields (the persona records a limitation).

**Versioning.** No `v3`. The additions are optional, no existing field changes meaning, and existing v2 fixtures already carry the provenance tags. ADR-016 records this and supersedes the `system_design.md` §7 note that expected a version bump.

**Seed-case completion.** Each of SC-01…SC-04 is populated from evidence already in the fixture or from an explicit synthetic value recorded in `synthetic_assumptions`. A mapping table is produced as stage evidence. SC-01's `credit_rating`/`pd` incoherence and SC-04's role label are resolved per clarification Q-1/Q-3. Verdicts and financial ratios are not rewritten.

## 3. Convergence core (P4-03)

### 3.1 Divergence

For each unordered persona pair `(i, j)`:

```text
rec_distance  = 0.0  if rec_i == rec_j
              = 0.5  if exactly one of the two is "conditional"
              = 1.0  if {rec_i, rec_j} == {approve, reject}
lean_distance = |lean_i - lean_j| / 2                     # in [0, 1]
pair_distance = 0.5 * rec_distance + 0.5 * lean_distance
pair_weight   = (confidence_i + confidence_j) / 2
divergence    = sum(w*d) / sum(w)     if sum(w) > 0
              = 1.0                   if sum(w) == 0       # fail-safe, not agreement
```

Three verdicts yield three pairs. The function is pure, takes no I/O, and returns a float in `[0,1]`. Escalation uses `divergence >= divergence_threshold` (the boundary belongs to escalation and is tested explicitly).

### 3.2 Tier 1 confidence proxies

Both are pure functions of bundle fields only (`pd`, `pd_band`, `rating_thresholds`).

**A — band dispersion.** `confidence_A = 1 - min(1, ((p90 - p10) / p50) / ref)`, with `ref = band_dispersion_ref` (proposed `2.0`). If `p50 <= 0`, return `0.0` (fail-safe: an undefined relative width is not high confidence).

**B — rating-boundary margin.** Let the bucket containing `pd` have finite bounds `[L, U]`; `confidence_B = min(1, min(pd - L, U - pd) / ((U - L) / 2))`, i.e. `0.0` exactly on a boundary and `1.0` at the bucket center. For the extreme open-ended buckets, use the single finite boundary and normalize by the nearest finite bucket's half-width. If `pd` is outside all configured bounds, return `0.0`.

**Selection protocol.** Run both over the seed cases at Stage 2 and record the table. The approved criterion ("separate the low-confidence case without flagging SC-01") is currently unsatisfiable — see `spec.md` Q-1; Stage 2 uses the criterion the owner selects at approval. Expected qualitative check after repair: high-confidence case ≥ threshold, low-confidence case < threshold. Thresholds are provisional; no accuracy claim is made.

### 3.3 Escalation

`escalate(...)` takes validated verdicts (or missing-persona markers), divergence, the selected Tier 1 confidence, and fallback provenance, and returns `(status, reasons)` per `spec.md` §4. Precedence is fixed: `incomplete` (any persona failed/bound breached) > `escalate` > `success`. Reasons are an enum of stable codes so the trace and tests assert on codes, not prose.

## 4. Persona workers (P4-02)

**Prompt composition.** A single `digest.py` renders the bundle into a deterministic, persona-neutral evidence digest (typed fields only; `None` rendered as an explicit "not available" marker, never as zero). Each persona module adds only its own rubric and role framing. The three builders share no mutable state and take the same `EvidenceBundle`; no builder accepts another persona's output.

**Rubric mapping.** CRO: `p90_pd`, `covenant_flags`, `credit_rating`. Growth: `revenue_growth_rate`, `pipeline_value_estimate`, `financial_ratios` (context only). Capital: `concentration_flag`, `p90_pd`, `credit_rating`, `financial_ratios` (context only). A persona whose field is `None` must add a `limitations` entry.

**Invocation.** `persona_worker.run(persona, bundle, gateway, config, correlation_id)`:

1. Build `GatewayRequest` with `json_mode=True`, `temperature=0.0`, `max_tokens=max_tokens_per_persona`.
2. Call `GatewayService.complete`; record attempt data for the trace.
3. `with_bounded_repair(call, parse_persona_verdict, max_repairs=1)`, where the second `call()` re-asks once and appends a one-line note that the previous reply did not match the schema (no raw invalid output is echoed back).
4. Enforce the per-persona attempt budget; return a typed `PersonaResult` (`verdict | failure_reason`) plus attempt metadata.
5. Never retain or forward another persona's context.

**Isolation.** Enforced structurally (each builder only receives the bundle and its own rubric) and asserted by a test that inspects the outbound `GatewayRequest` for each persona and fails if any other persona key, verdict, or rationale appears.

### 4.1 Lean anchor table (proposed; approval item Q-4)

`lean` is the persona's directional support for extending credit under its mandate, independent of the categorical recommendation:

| lean | Anchor |
| --- | --- |
| `+1.0` | Mandate strongly favors approval; no material mitigant. |
| `+0.5` | Favorable, with identified but manageable concerns. |
| `0.0` | Genuinely balanced; cannot lean either way on available evidence. |
| `-0.5` | Opposed, though specific mitigants could change the view. |
| `-1.0` | Mandate strongly opposes; material unmitigated risk or breach. |

Intermediate values are interpolations. The rubric states explicitly that `lean` and `recommendation` are separate fields and may diverge; divergence consumes both.

## 5. Orchestration, report, trace (P4-04)

**Graph.** LangGraph `StateGraph` with a typed `Tier3State`: one `START` fan-out to the three persona nodes, a join, one convergence node (divergence → confidence → escalation), and one report node. Persona nodes are thin wrappers over `persona_worker.run`; the convergence and report nodes call pure functions. Exactly three LLM nodes exist; the graph is static (no dynamic routing, no agent-to-agent edges).

**Concurrency.** FR6 requires parallel persona invocation. The pinned LangGraph version's sync-vs-async branch execution semantics are verified at Stage 0 (bounded local spike, no production code). The gateway is synchronous; if the sync `invoke` path does not execute branches concurrently, persona nodes are offloaded with `asyncio.to_thread` under `ainvoke` **without modifying Phase 3 gateway code**. The chosen mechanism is recorded in the stage evidence before Stage 4.

**Report.** `build_report(bundle, verdicts, convergence)` returns a Markdown body plus a structured model. Sections: header (company, rating, PD, band — all bound to typed fields), convergence summary (divergence, threshold, confidence proxy + value, status), one attributed block per persona (rationale verbatim, `limitations` listed), and a review notice. No prose is generated; no number is formatted from anything but a typed field.

**Trace.** `Tier3Trace` holds correlation id, per-persona attempt records, gateway provider events, divergence inputs (the three verdict fields), divergence value, proxy used and value, outcome and reasons, plus `cost_unknown` when applicable. It is returned in memory only.

**Bounds.** The orchestration counts gateway calls (persona + repair), enforces `max_tokens_per_persona`, a 60 s wall-clock budget, and the cost cap. Reaching a limit stops the run and returns `incomplete`; completed personas are never used to render a partial report.

## 6. Configuration

`Tier3Config` mirrors the `params.yaml tier3` block in `spec.md` §3 with `extra="forbid", frozen=True` and explicit bounds (`divergence_threshold` and `tier1_confidence_threshold` in `[0,1]`, positive token/call/time/cost limits). `tier1_confidence_proxy` is a literal `{"band_dispersion", "rating_margin"}` updated by the Stage 2 selection. `calibration: "provisional-phase5"` is a literal that documents status, not a switch.

The `tier3` dependency group holds `langgraph` only (pinned). It is added to `[tool.uv] default-groups` so `uv sync` and CI install it, while the existing Dockerfile `uv sync --no-default-groups` keeps it out of the serving image.

## 7. Open details completed here (flagged, not decided)

| Item | Completed in this plan | Why it is flagged |
| --- | --- | --- |
| Proxy A normalizer `ref` | `band_dispersion_ref = 2.0`; `p50 <= 0` → `0.0` | D4-03 gave the formula but no reference scale or zero-median rule. |
| Proxy B normalization | Bucket half-width; `0.0` on a boundary | "Normalized distance" was unspecified. |
| Selection criterion | Not changed — `spec.md` Q-1 asks the owner | The approved test is unsatisfiable on the current seed set. |
| ADR-016 timing | Drafted and submitted at Stage 1 | Implementation plan says "at approval"; implementation evidence is needed first. |
| Unknown cost | Fail-safe escalation + trace flag (Q-2) | D4-07 covers only an exceeded cap. |

Everything else follows an approved decision directly.

## 8. Test strategy

- **Contract:** field validation, `None` preservation, provenance/derivation rules, `limitations` round-trip, v1 and Tier 1/Tier 2 non-regression.
- **Properties (divergence):** range, permutation invariance, symmetry, monotonicity in lean spread, zero-weight fail-safe, boundary at `>= threshold`.
- **Proxies:** analytic cases (boundary = 0, bucket center = 1, `p50 = 0`, out-of-range `pd`).
- **Truth table:** every row of `spec.md` §4, including fallback provenance and bound breach; assert reason codes.
- **Workers:** mocked gateway only — success, one-repair recovery, double failure, isolation, uniform temperature, request shape.
- **Graph/report:** fake gateway end-to-end for converge, diverge, incomplete; numeric traceability assertions; incomplete → `report is None`.
- **Offline harness:** replay SC fixtures through the real divergence/escalation/report path; no network.
- **Optional live smoke:** env-gated (`ACRAS_LIVE_GATEWAY_SMOKE=1`), never a gate, never in CI.

## 9. Traceability

| Requirement | Tasks | Stage | Primary evidence |
| --- | --- | --- | --- |
| T3-FR-01…04 | T3-T02…T05 | 1 | `test_contract_fields.py`; fixture mapping table |
| T3-FR-10…14 | T3-T06…T09 | 2 | `test_divergence.py`, `test_tier1_confidence.py`, `test_escalation.py` |
| T3-FR-05…09 | T3-T10…T12 | 3 | `test_persona_worker.py`; isolation test; data-flow correction |
| T3-FR-15…18 | T3-T13…T15 | 4 | `test_tier3_graph.py`, `test_tier3_report.py`; trace assertions |
| Exit criteria 1–7 | T3-T16 | 5 | extended `test_offline_harness.py`; full suite + Ruff + Pyright |

## 10. Risks and deferrals

- **Seed-set evidential power (material):** four synthetic cases cannot validate either proxy or any threshold; Phase 5 owns calibration. Recorded as a limitation, not hidden.
- **Fixture edits:** Q-3 requires owner approval; without it P4-02 has no typed rubric evidence to read.
- **LangGraph concurrency:** verified at Stage 0; a serial sync fan-out would break the latency intent and trigger the change protocol before Stage 4.
- **Cost telemetry:** if a provider omits usage, cost is unknown and Q-2 governs.
- **Deferred by design:** durable trace (Phase 6), promotion gate and golden set (Phase 5), qualitative grounding (D-06 evidence-first).
