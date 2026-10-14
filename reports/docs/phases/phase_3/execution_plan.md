# ACRAS Phase 3 — Staged Execution Plan

**Phase:** 3 — LLM Gateway & Provider Resilience  
**Status:** ✅ Approved 2026-10-12; awaiting implementation authorization  
**Implementation authorization:** Not granted — explicit go required  
**Planning baseline:** Phase 2 closed 2026-10-08; Phase 3 repository baseline must be re-verified at Stage 0.

## Purpose and execution discipline

This plan translates the approved Phase 3 Implementation Plan and feature SDDs into a sequential, evidence-gated implementation sequence. It introduces no architectural decisions. Decisions already accepted in the architecture record are constraints to implement, not new ADRs to create again.

Each stage has a hard gate. **No work in the next stage begins until the current stage's gate passes and its evidence is recorded.** A failed, partial, or undocumented stage remains open. If repository evidence or implementation work exposes a material decision not covered by the approved plan, stop the affected stage and return to the decision workflow; do not silently choose a workaround.

Falsification is selective: use a controlled negative test when it proves a gate or failure-handling path actually detects a fault. Documentation and baseline-audit stages do not require artificial code failures.

## 1. Execution preconditions

The following must be satisfied before Stage 0 starts:

- [x] Overall Phase 3 Implementation Plan explicitly approved 2026-10-12 (verified in plan §10).
- [x] Both feature SDDs (`001_llm_gateway` and `002_provider_resilience`) explicitly approved 2026-10-12, including their contracts, failure policy, tasks, and validation criteria.
- [x] Clarification decisions are resolved and recorded 2026-10-12; no material provider, schema, secret, retry, breaker, or error-handling question remains open.
- [x] ADR-034 is accepted and consolidated in `reports/docs/architecture/system_design.md` §6 (verified 2026-10-12); ADR-009 body intact, supersession noted on its status line only.
- [x] Implementation authorization explicitly granted after plan approval.
- [x] Repository SDD, source-module, test, and configuration paths confirmed from the live repository 2026-10-12 (SDDs, `src/gateway/` scaffold, `params.yaml`, `tests/{unit,benchmarks}` all present).
- [x] Gemini primary confirmed as `gemini-2.5-flash` (200 ×2 at ~1.3–2.2s vs 15s budget, usage metadata, clean 400 on malformed) — full evidence in D3-02.
- [x] Groq fallback pin confirmed as `openai/gpt-oss-20b` at `https://api.groq.com/openai/v1` via `GROQ_API_KEY` (200 ×2 at ~410ms, usage metadata, clean 400 on malformed; browser-style `User-Agent` required) — full evidence in D3-02.
- [x] Credential hygiene verified 2026-10-12 (repo-wide secret-pattern scan clean; operator holds keys out-of-band). Standing rule for all stages.

If any precondition is unmet, execution does not begin.

## 2. Stage index

| Stage | Name | Primary deliverable | ADR Implements | Falsification | Hard gate |
|---|---|---|---|---|---|
| 0 | Repository Baseline & Preconditions | Verified baseline and path/config map | None new | Reconcile reported assumptions against repository evidence | Preconditions and baseline checks all pass; no production code changed |
| 1 | Gateway Contracts & Configuration | Approved typed contracts and validated non-secret config | None new | Invalid bounds, unknown fields, and missing required config are rejected | Contract/config tests pass; secret resolution is isolated; v1 schema unchanged |
| 2 | Gemini Primary Adapter | Thin primary-provider adapter behind shared transport | None new | Mock success, timeout, non-2xx, and malformed responses | Normalized success/error behavior and bounded timeout proven |
| 3 | Groq Fallback Adapter | Pinned Groq adapter and qualification record | None new | Missing auth, HTTP errors, malformed response, and missing usage fields | Correct route/model/header/auth convention and normalized responses proven |
| 4 | Structured Provider Events & Redaction | Versioned event model and standard-library logging integration | None new | Inject prompt/response/secret-like values and inspect emitted logs | Required fields are present; sensitive content is absent; unknown usage/cost remains unknown |
| 5 | Circuit Breakers & Failure Classification | Independent provider breakers and explicit eligible-failure policy | None new | Force threshold crossing, open state, and recovery probe | State transitions and failure classes match approved policy and pinned `pybreaker` semantics |
| 6 | Gateway Routing & Bounded Outcomes | End-to-end primary → fallback orchestration | None new | Force primary outage and dual-provider failure | One primary + at most one fallback attempt; typed controlled outcome; no unhandled provider exception |
| 7 | Resilience & Integration Acceptance | Permanent outage, recovery, routing, and redaction tests | None new | Break a key routing/event assertion in a controlled test variant to prove test sensitivity | Required fault scenarios pass deterministically without live provider calls in routine CI |
| 8 | Full Regression, Security & Quality Gate | Complete validation evidence and non-interference proof | None new | Verify regression suite fails on a controlled boundary violation where practical | Full tests, Ruff, Pyright, security checks, and deterministic-tier comparisons pass |
| 9 | ADR Consolidation, PIR & Phase Sign-off | Closed implementation record and next-phase boundary | None new — consolidate existing decisions only | Audit recorded claims against test output, diffs, and qualification evidence | Every exit criterion has evidence; PIR complete; human Phase 3 sign-off recorded |

## 3. Detailed stages

### Stage 0 — Repository Baseline & Preconditions

**Goal**  
Establish the actual repository state, verify all execution approvals, and resolve any mismatch between this plan, the feature SDDs, and the codebase before implementation begins.

**Actions**

1. Verify the working tree, current branch, and repository status; record the starting commit.
2. Re-run `uv run pytest`, `uv run ruff check .`, and `uv run pyright`; record exact counts, skips, warnings, and exit codes rather than copying prior reported results.
3. Inspect `pyproject.toml` and lockfile; confirm `httpx`'s current dependency group and determine the exact approved dependency change needed for runtime use.
4. Inspect `src/gateway/`, existing configuration loading, `params.yaml`, environment-secret conventions, and standard-library rotating logger setup.
5. Confirm test directory conventions and the actual SDD path convention; replace provisional file paths in the approved tasks before coding.
6. Verify Phase 2 exit/PIR references and current `EvidenceBundle` v1 validators; capture baseline tests or representative deterministic outputs for later comparison.
7. Verify the Gemini primary live (model `gemini-2.5-flash`, endpoint, request/response format, `GEMINI_API_KEY` auth) with the same qualification discipline as the Groq leg — minimal completion + malformed legs, sanitized evidence — because no authoritative configuration exists to verify against. Do not build the Stage 2 adapter on documentation alone. Confirm Groq route/model/header/auth requirements against the accepted qualification record.
8. Record any mismatch as a blocker. Do not modify production code to make the baseline match this plan.

**ADR Implements**  
None new. This stage verifies the baseline and the applicability of already accepted decisions; it does not establish architecture.

**Falsification**  
No artificial code fault. The falsification method is an evidence reconciliation: if a reported assumption (for example, the empty gateway scaffold, dependency placement, or current baseline) does not match repository evidence, the stage fails and must be reconciled.

**Gate 0 — Baseline accepted**  
All preconditions and approvals are evidenced; test/static-check results and starting commit are recorded; repository paths and Gemini configuration are verified; all discrepancies are resolved or formally returned to planning; no production code has changed.

---

### Stage 1 — Gateway Contracts & Configuration

**Goal**  
Define the stable provider-neutral boundary and validated operational configuration before implementing provider-specific HTTP behavior.

**Actions**

1. Implement the approved Pydantic request and result contracts from `001_llm_gateway/spec.md`; use the exact approved message/input shape and correlation/request identifier convention.
2. Implement the approved typed usage, provider-error, and provider-event contracts, separating provider details from the gateway's public outcome.
3. Define explicit error categories sufficient to distinguish caller/input validation, local configuration/authentication faults, timeout/connection faults, retryable provider failures, malformed provider responses, and controlled dual-provider failure.
4. Add the approved gateway configuration section to the repository's confirmed configuration source. Keep provider/model identifiers and bounded resilience settings non-secret; resolve credentials from the approved environment/secret convention.
5. Enforce bounds and reject unknown configuration fields where required by the project standard. Do not put credentials in `params.yaml` or other version-controlled files.
6. Add unit tests for valid parsing, invalid bounds, missing required values, unknown fields, missing secrets, and stable typed error behavior.
7. Confirm gateway contracts do not alter or extend `EvidenceBundle` v1; Phase 4 owns Tier 3 schema changes.

**ADR Implements**  
None new. Implement the contract and configuration choices explicitly approved in the Phase 3 plan/SDD. If implementation requires a new material contract decision, stop and return to planning.

**Falsification**  
Inject out-of-range timeouts/thresholds, an unknown config field, and a missing required provider setting. Confirm validation fails closed before any network call. Use a sentinel secret and confirm it is not included in serialized errors or validation messages.

**Gate 1 — Contract/config boundary is enforced**  
Approved models and config parse valid inputs; invalid and unknown settings are rejected; secrets are resolved only from the approved secret source and do not appear in error output; tests pass; `EvidenceBundle` v1 and deterministic-tier interfaces are unchanged.

---

### Stage 2 — Gemini Primary Adapter

**Goal**  
Implement and test the Gemini primary-provider adapter behind the shared transport without leaking provider-specific request/response details into gateway callers.

**Actions**

1. Implement the thin Gemini adapter using the endpoint, model ID, authentication convention, and request/response shape verified at Stage 0 and approved in the SDD.
2. Use the shared injectable `httpx` transport and explicit primary timeout; ensure there are no hidden adapter-level retries.
3. Normalize successful provider responses into the approved gateway result contract, including finish/status metadata and usage fields when actually returned.
4. Normalize timeout, connection, non-success HTTP status, provider error body, and malformed/empty response into the approved error categories.
5. Sanitize error details before they can reach logs or public gateway results; do not log raw request/response bodies or credentials.
6. Add deterministic mock-transport tests for successful response parsing, timeout, connection error, representative 4xx/5xx, malformed JSON, missing required response fields, and usage absent/present.
7. Keep live provider qualification outside routine CI; use only explicitly authorized, credential-safe qualification runs.

**ADR Implements**  
None new. The adapter implements the already approved Gemini-primary and shared-transport decisions. No provider SDK or framework is added unless a new decision is approved first.

**Falsification**  
Return a malformed body and simulate a timeout and 5xx response through the mock transport. Each must become the correct normalized failure; no raw provider exception or response payload may escape the adapter contract.

**Gate 2 — Primary adapter is bounded and normalized**  
Mocked success and failure tests pass; configured timeout is enforced; retries remain zero; normalized outputs conform to the approved Pydantic contract; sensitive payloads are not emitted; no live provider is required for CI.

---

### Stage 3 — Groq Fallback Adapter & Qualification

**Goal**  
Implement the approved Groq-direct fallback with a fixed model pin and verify its transport contract, authentication, and operational assumptions.

**Actions**

1. Implement the Groq adapter using `https://api.groq.com/openai/v1` and model `openai/gpt-oss-20b`; do not reopen the closed Llama/Mistral selection unless new evidence invalidates the accepted decision.
2. Read credentials only from `GROQ_API_KEY`; confirm missing credentials fail in a controlled way and never expose the key.
3. Include the required browser-style `User-Agent` header as documented in the qualification evidence and assert its presence in transport tests.
4. Reuse the shared `httpx` transport and approved fallback timeout; do not add hidden retries.
5. Normalize completion content, response status, finish metadata, and usage fields into the same gateway result contract used by Gemini.
6. Cover HTTP 400/401/403/429/5xx, timeout, connection failure, malformed or empty completion, and absent usage metadata with mocked tests.
7. Perform the approved limited live qualification separately from CI, recording date, exact route/model, response status, measured latency, usage metadata availability, and any free-tier limitations. Do not record credentials or sensitive prompt/response content.
8. Keep actual cost unknown unless it can be computed from trustworthy usage data and an explicit, versioned rate source. Do not treat current free-tier access as permanent production pricing.

**ADR Implements**  
None new. The provider/model decision is already recorded in accepted ADR-034; this stage implements and verifies it rather than creating a duplicate ADR.

**Falsification**  
Simulate missing auth, a rejected request, malformed completion, and a successful response with no usage metadata. Verify correct normalized errors and that missing usage/cost remains unknown rather than becoming zero. Verify the request contains the pinned model and required `User-Agent`.

**Gate 3 — Fallback adapter qualified**  
The configured route and exact model pin are correct; authentication/header behavior is tested; success and required failure modes normalize correctly; qualification evidence is recorded without secrets; the fallback timeout and zero-retry policy are enforced. If the provider no longer meets the accepted contract, stop and return to planning.

---

### Stage 4 — Structured Provider Events & Redaction

**Goal**  
Provide the minimum versioned, auditable event stream needed to observe provider selection, failure, fallback, breaker state, latency, and trustworthy usage/cost evidence without adding a telemetry platform.

**Actions**

1. Implement the approved versioned provider-event model with fields for correlation/request ID, provider, model, attempt number, outcome/error category, latency, fallback decision, breaker state/transition, and usage/cost availability.
2. Emit events through the existing standard-library logging path. Do not add OpenTelemetry, Prometheus, MLflow serving tracking, or a new observability service in Phase 3.
3. Ensure usage fields distinguish unavailable/unknown from measured zero; cost is populated only when computable from trustworthy usage and an explicit rate source.
4. Apply an allowlist for logged fields. Exclude prompt content, completion content, raw provider bodies, credentials, and sensitive borrower data.
5. Ensure event emission failures do not mask the primary gateway outcome, while making logging failures observable through a safe fallback mechanism consistent with existing project logging standards.
6. Add captured-log tests for primary success, fallback success, timeout, dual failure, breaker transition, usage present/absent, and sanitized provider errors.

**ADR Implements**  
None new. Implement the already approved minimal structured logging design; do not expand scope into a general observability architecture.

**Falsification**  
Inject recognizable sentinel strings representing a prompt, response, API key, and sensitive borrower field into test inputs/errors. Assert none appears in captured logs while required event metadata is present. Assert unknown usage/cost is serialized as unknown/null according to the approved schema, not `0`.

**Gate 4 — Events are useful and redacted**  
All required event fields are emitted for the covered outcomes; correlation and attempt data are stable; redaction tests pass; unknown usage/cost remains unknown; logs use the existing logger and introduce no new telemetry platform.

---

### Stage 5 — Circuit Breakers & Failure Classification

**Goal**  
Implement independent provider breaker behavior and explicit classification of failures eligible for fallback, with semantics verified against the selected `pybreaker` version.

**Actions**

1. Add `pybreaker` only through the approved dependency/lockfile change and record the exact resolved version.
2. Configure separate breaker instances for Gemini and Groq, with the approved initial values: three consecutive eligible failures, 30-second open/reset interval, one half-open probe per provider, and no same-provider retries.
3. Confirm whether the breaker is process-local for this phase and document that operational boundary; do not imply cross-process coordination.
4. Define and implement the approved failure matrix for timeout, connection failure, eligible server error, rate limit, authentication/configuration error, malformed response, local input error, and breaker-open state. Follow the approved clarification answers; do not silently broaden eligibility.
5. Ensure a breaker-open primary is treated as a primary failure eligible to route to the fallback without sending a primary request.
6. Test closed → open → half-open → closed recovery, repeated failure reopening, independent state between providers, and single-probe semantics.
7. Check the selected library's actual exception and half-open behavior against its pinned version; wrap or adapt it only as needed to preserve the approved gateway semantics.

**ADR Implements**  
None new. This stage implements the already approved breaker/fallback policy. Any required change to thresholds, state scope, or failure eligibility must return to the decision workflow before code continues.

**Falsification**  
Force three eligible consecutive failures and confirm the provider breaker opens; verify the next request does not call that provider. Advance the configured interval under deterministic test control, allow one probe, and prove successful recovery closes the breaker while a failed probe reopens it. Verify one provider's breaker does not change the other provider's state.

**Gate 5 — Breaker semantics match policy**  
Pinned `pybreaker` behavior is verified; both provider breakers transition as approved; failure eligibility is covered by tests; half-open probe behavior is bounded; no hidden retries or cross-provider state coupling exists.

---

### Stage 6 — Gateway Routing & Bounded Outcomes

**Goal**  
Integrate the contracts, provider adapters, events, and breakers into one gateway call path with bounded attempts and a controlled typed result for dual failure.

**Actions**

1. Implement the gateway orchestration entry point using the approved request and result/error contracts.
2. Attempt the primary once when its breaker permits; return immediately on success without calling the fallback.
3. On an approved fallback-eligible primary failure or open breaker, record the event and attempt the fallback at most once if its breaker permits.
4. Enforce the maximum of two provider attempts per gateway call: one primary and one fallback; no same-provider retry and no recursive fallback.
5. Return a normalized success identifying the actual provider/model used, or a controlled typed gateway failure if both providers fail/open. Do not expose raw provider exceptions as the public contract.
6. Preserve causal error context in sanitized form without leaking request bodies, secrets, or sensitive data.
7. Confirm the gateway is independent of Tier 1/Tier 2 implementation and does not write LLM output into `EvidenceBundle` v1 or deterministic calculations.
8. Add focused unit tests for primary success, fallback success, fallback unavailable/open, both providers failing, and controlled error propagation.

**ADR Implements**  
None new. This stage realizes existing gateway, circuit-breaker, and fallback decisions in ADR-006/ADR-009/ADR-034; it creates no new ADR unless a genuinely new material decision is approved through change management.

**Falsification**  
Force primary timeout and fallback failure. Assert exactly two attempts at most, a typed controlled failure is returned, the failure event is emitted, and no raw transport exception escapes. In the primary-success case, assert the fallback transport receives zero calls.

**Gate 6 — Gateway routing is bounded**  
Primary success bypasses fallback; eligible primary failure routes to fallback; dual failure returns the approved typed outcome; no call exceeds two provider attempts; all outcomes emit redacted events; no deterministic-tier or EvidenceBundle v1 changes occur.

---

### Stage 7 — Resilience & Integration Acceptance Tests

**Goal**  
Turn the approved failure policy into a permanent, deterministic acceptance suite that proves outage handling, recovery, event accuracy, and the provider boundary.

**Actions**

1. Add integration tests using mock transports/fakes only; routine CI must not require live provider credentials or call external providers.
2. Cover primary success, primary timeout, connection failure, eligible HTTP failure, 429 policy, authentication/configuration failure policy, malformed response policy, fallback success, fallback failure, both breakers open, and dual-provider failure.
3. Cover breaker closed/open/half-open/recovery behavior and confirm the per-provider state isolation and probe concurrency semantics selected in the SDD.
4. Assert attempt counts and timeout bounds, including no hidden retries and no third attempt.
5. Assert event completeness, correlation identifiers, attempt order, provider/model used, breaker transitions, redaction, and unknown usage/cost behavior.
6. Test repeated requests after recovery and verify a recovered primary is used according to the approved breaker policy.
7. Keep any live provider smoke test opt-in, explicitly labeled, secret-safe, and separate from required CI.

**ADR Implements**  
None new. This stage makes existing decisions executable as regression protection.

**Falsification**  
Temporarily invert or disable one critical assertion in a local test variant (for example, assert fallback is not called after a forced primary timeout). Confirm the deliberately incorrect expectation fails against the real implementation, then discard the mutation. Do not commit the mutation or weaken the permanent test.

**Gate 7 — Reliability behavior proven**  
All required failure/recovery scenarios pass deterministically; test coverage proves attempt bounds and state transitions; no routine test makes a live provider call; event and redaction assertions pass; any failure leaves the stage open.

---

### Stage 8 — Full Regression, Security & Quality Gate

**Goal**  
Demonstrate that the completed gateway satisfies Phase 3 requirements without regressing existing deterministic Tier 1–2 behavior, the EvidenceBundle v1 contract, or project quality controls.

**Actions**

1. Run the complete test suite and record exact passed/failed/skipped counts and duration.
2. Run Ruff and Pyright with zero-error acceptance; resolve newly introduced warnings/errors rather than suppressing them without approval.
3. Compare `EvidenceBundle` v1 fields/validators and deterministic Tier 1–2 representative outputs against Stage 0 evidence; investigate any difference.
4. Verify no LLM result is passed into PD, rating, Monte Carlo simulation, or other deterministic calculation paths.
5. Inspect dependency/lockfile diffs to ensure only approved runtime dependencies and transitive changes were introduced; no SDK/framework was added without approval.
6. Inspect source, tests, configuration, and logs for credentials, prompts, responses, borrower-sensitive data, and accidental secrets.
7. Verify usage/cost semantics, provider pin, timeout/attempt bounds, and logging event schema against the accepted plan and SDD.
8. Record test commands, exact outputs, commit/diff references, qualification evidence, and any residual non-blocking findings.

**ADR Implements**  
None new. This is a conformance and regression stage, not a decision-making stage.

**Falsification**  
Where practical, run a controlled boundary regression (such as a temporary test fixture that attempts to route a gateway result into a deterministic calculation) and confirm the boundary check/test blocks it. Remove the mutation afterward. Do not falsify production behavior or accept unexplained baseline changes.

**Gate 8 — Regression and non-interference proven**  
Full pytest passes; Ruff and Pyright pass with zero errors; no unexplained baseline regressions; EvidenceBundle v1 and deterministic Tier 1–2 behavior remain unchanged; security/redaction review passes; dependency changes match approval; all required evidence is recorded.

---

### Stage 9 — ADR Consolidation, PIR & Phase Sign-off

**Goal**  
Close the loop between approved decisions, implementation, validation evidence, and the authoritative project record before Phase 4 planning begins.

**Actions**

1. Reconcile the final implementation and dependency diff against the approved Phase 3 Implementation Plan, both SDDs, accepted ADRs, invariants, and execution-stage gates.
2. Verify accepted ADR-034 is present in `reports/docs/architecture/system_design.md` §6 (already consolidated 2026-10-12; verify-only). Preserve its scope: Groq-direct fallback pin only; do not silently rewrite ADR-009's custom gateway, `pybreaker`, or Gemini-primary decisions.
3. Verify that ADR cross-references accurately describe the fallback designation supersession and that no stale HF-fallback references remain in active Phase 3 planning artifacts. Preserve historical records when appropriate; correct active normative references only through the approved documentation workflow.
4. Update architecture/status records to mark Phase 3 complete only after all exit criteria pass.
5. Complete every Post-Implementation Review row in the Phase 3 Implementation Plan with actual test results, measured behavior, provider qualification evidence, deviations, and exact references. No `_pending_` row may remain unless a formally approved exception explains why.
6. Verify all Phase 3 exit criteria: primary success, automatic fallback on forced eligible failure/timeout, controlled dual failure, breaker transitions, bounded attempts, event/redaction guarantees, Groq pin/qualification, unchanged deterministic tiers and EvidenceBundle v1, full regression quality gates.
7. Record unresolved risks and explicit ownership. A material unresolved requirement blocks closure; it cannot be relabeled non-blocking without approval.
8. Obtain explicit human Phase 3 sign-off. Phase 4 remains a separately scoped and approved phase; do not start persona implementation as part of this closure stage.

**ADR Implements**  
None new. Consolidate and cross-check existing accepted ADRs only. If implementation requires a genuinely new architectural decision, return to the decision workflow and add an ADR only after approval.

**Falsification**  
No artificial code fault. Conduct a documentation-to-reality audit: trace each exit claim to a specific test/result, configuration, diff, or provider qualification record. Any unsupported claim fails the gate.

**Gate 9 — Phase 3 closed; Phase 4 may enter its own planning workflow**  
All stages 0–8 have passed; all exit criteria are backed by evidence; the PIR is complete; accepted ADRs and active cross-references are consistent; architecture/status records reflect actual implementation; no material unresolved finding remains; human Phase 3 sign-off is recorded. Phase 4 implementation is not authorized by Phase 3 closure alone.

## 4. Global execution controls

- Stages are strictly sequential. No later stage starts while an earlier gate is failed, partial, awaiting approval, or awaiting remediation.
- Use the approved workflow: analyze → challenge → recommend → human decides → plan → human approves → implement → validate → report.
- Work only from approved SDD tasks. Stop after each task or approved task batch, present the diff and evidence, and obtain the required human approval before proceeding.
- A material scope, architecture, provider, security, latency, cost, or contract change stops the affected stage and returns to the decision workflow.
- Keep credentials out of source, YAML, prompts, test fixtures, logs, chat, and generated artifacts.
- No live provider calls in routine CI.
- Do not change `EvidenceBundle` v1, deterministic Tier 1–2 calculations, Phase 4 persona behavior, or Phase 5 evaluation gates in Phase 3.
- Unknown provider usage/cost must remain unknown; do not infer zero or promise permanent free-tier access.
- The gateway must not make claims about semantic equivalence between Gemini and Groq. Provider quality evaluation belongs to later phases.

## 5. Phase 3 acceptance evidence checklist

- [ ] Primary success returns a normalized result and does not call fallback.
- [ ] Forced eligible primary failure/timeout invokes Groq fallback.
- [ ] Both-provider failure produces a controlled typed outcome, not a raw provider exception.
- [ ] Attempt count is bounded to one primary plus at most one fallback; same-provider retries are zero.
- [ ] Independent breaker closed/open/half-open/recovery behavior is proven against the pinned library version.
- [ ] Required event fields are present for success, failure, fallback, and breaker transitions.
- [ ] Logs contain no prompt, response, credential, raw provider body, or sensitive borrower data.
- [ ] Usage and cost are captured only when trustworthy; unavailable values remain unknown.
- [ ] Groq route/model/auth/header are verified; qualification evidence does not include secrets.
- [ ] Gemini model/endpoint/auth configuration is verified and recorded.
- [ ] Full tests, Ruff, and Pyright pass; any skips are explained.
- [ ] `EvidenceBundle` v1 and deterministic Tier 1–2 behavior are unchanged.
- [ ] Dependency changes are minimal and approved; no unapproved provider framework/SDK is introduced.
- [ ] ADR-034 and cross-references are consolidated accurately; ADR-009 is not silently rewritten.
- [ ] Phase 3 PIR is complete and human sign-off is recorded.

## 6. Approval and stage record

| Artifact / control | Status |
|---|---|
| Overall Phase 3 Implementation Plan | ✅ Approved 2026-10-12 (all clarifications, SDDs, and this plan) |
| `001_llm_gateway` SDD | ✅ Approved 2026-10-12 |
| `002_provider_resilience` SDD | ✅ Approved 2026-10-12 |
| Execution Plan | ✅ Approved 2026-10-12 (with Gemini-live-verification requirement) |
| Implementation authorization | Not granted — explicit go required |
| Stage 0 | Not started |
| Stages 1–9 | Blocked pending Stage 0 and preceding gates |
