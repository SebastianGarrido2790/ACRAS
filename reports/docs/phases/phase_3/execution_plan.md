# ACRAS Phase 3 — Execution Plan
**Status:** Draft for human review; not approved for execution. **Implementation authorization:** Not granted.

## Purpose
Translate the approved Phase 3 implementation plan into sequential gated stages. This plan introduces no new architecture decisions.

## 1. Preconditions
- [ ] Overall Phase 3 plan approved.
- [ ] ADR-034 accepted in `reports/docs/architecture/system_design.md` §6 with the supplied Groq qualification evidence.
- [ ] D3-05 gateway contract and D3-06 acceptance/test matrix reviewed through the feature SDDs and this plan.
- [ ] Repository SDD/module/test paths confirmed.
- [ ] Baseline rerun: pytest, Ruff, Pyright, EvidenceBundle v1 and deterministic-tier checks.
- [ ] Gemini primary model/endpoint and environment variable convention verified from project authority.
- [ ] Required credentials are supplied out-of-band; no values shared or committed.
- [ ] Dependency/lockfile changes are included in approved tasks.

## 2. Stage index
| Stage | Goal | Gate | Falsification |
|---|---|---|---|
| 0. Baseline verification | Establish actual repository state | Baseline and paths recorded; discrepancies resolved | Compare reported baseline and empty gateway assumptions to live files |
| 1. SDD approval | Lock contracts and failure semantics | Clarification answers and explicit human approvals recorded | Adversarial review for contradictions and untestable requirements |
| 2. Contract/config | Typed contracts and safe config | Contract/config tests pass; no secret leakage | Inject invalid config and secret-like values |
| 3. Adapters/events | Normalize Gemini/Groq calls and emit events | Mocked success/error/timeout/redaction tests pass | Inject malformed JSON, 4xx/5xx and missing fields |
| 4. Resilience | Failover and breaker state | Primary failure reaches fallback; two-attempt bound and transitions pass | Force primary timeout and fallback outage |
| 5. Acceptance/regression | Prove whole path and non-interference | Full tests, Ruff, Pyright and tier/schema checks pass | Disable a routing/event assertion and prove tests fail |
| 6. Closure | Complete PIR and ADR consolidation | Every exit criterion has evidence and human sign-off | Audit criteria against exact test/result references |

Stages are sequential. Stage 2 onward is blocked until Stage 1 approval. No implementation begins while overall plan approval is pending.

## 3. Stage details

### Stage 0 — Baseline verification
Inspect gateway, `pyproject.toml`, lockfile, `params.yaml`, config/secret conventions, logger, test layout, ADR index and SDD path convention. Run current checks and record exact counts/skips. Confirm EvidenceBundle v1 and deterministic outputs. Verify authoritative Gemini model/endpoint. **Gate:** baseline and conventions recorded; conflicts reconciled; no production code changed.

### Stage 1 — Contract approval
Answer both spec clarification gates. Review Pydantic request/result/usage/error/event schemas, error eligibility, 429/auth/malformed response handling, breaker scope/half-open semantics, task sequence and paths. **Gate:** no unresolved material contract/policy decision; human approvals recorded.

### Stage 2 — Contract/config
Implement approved contracts, validated non-secret configuration and secret resolution. **Dependencies:** Stage 1. **Gate:** focused tests pass, no secrets in errors/logs, EvidenceBundle v1 unchanged.

### Stage 3 — Adapters/events
Implement Gemini and Groq adapters with injectable `httpx`, Groq model `openai/gpt-oss-20b`, `GROQ_API_KEY`, browser-style User-Agent, normalized usage/errors and redacted events. **Dependencies:** Stage 2 and verified Gemini route. **Gate:** mocked success, malformed, non-2xx, timeout, usage-known/unknown and redaction tests pass. Live qualification is separate from CI.

### Stage 4 — Resilience
Implement one primary plus one fallback attempt, approved timeouts, zero retries, independent `pybreaker` instances and classified failures. **Dependencies:** Stage 3 and approved policy answers. **Gate:** deterministic tests prove primary success skips fallback; timeout/failure triggers fallback; open/half-open/recovery works; dual failure is controlled; no third attempt.

### Stage 5 — End-to-end acceptance
Run all new tests, full pytest, Ruff and Pyright. Compare EvidenceBundle v1 and deterministic Tier 1–2 outputs with Stage 0. Inspect logs for sensitive data; verify unknown usage/cost remains unknown. **Gate:** all required tests pass and any baseline deviation is explained/approved.

### Stage 6 — Closure
Map every exit criterion to exact tests/results/qualification evidence; complete PIR with no `_pending_` unless a formally accepted exception exists; consolidate ADR-034 in `system_design.md` §6; verify ADR-009 is not silently rewritten and its fallback designation is explicitly superseded; sweep stale HF references; obtain Phase 3 sign-off. **Gate:** all criteria satisfied or explicitly blocked with accepted rationale. Phase 4 remains separately planned/approved.

## 4. Global controls
- One task per isolated agent session; stop after each task, present diff and validation evidence, and wait for human approval.
- Do not start a task with unresolved dependencies.
- Material architecture/scope/security/cost/latency change stops the affected stage and returns to decision workflow.
- No secrets in source, YAML, chat, logs, prompts or artifacts.
- No live provider calls in routine CI.
- Do not change EvidenceBundle v1, deterministic Tier 1–2 calculations or Phase 4 persona behavior in Phase 3.

## 5. Acceptance evidence checklist
- [ ] Primary success skips fallback.
- [ ] Forced primary failure/timeout invokes Groq fallback.
- [ ] Dual failure is controlled and typed.
- [ ] Breaker open/half-open/closed and recovery proven.
- [ ] Two-attempt and timeout bounds proven.
- [ ] Events record provider/model, outcome, latency, fallback/breaker, correlation and usage/cost known state.
- [ ] Redaction tests prove no prompts, responses, secrets or sensitive payloads in logs.
- [ ] Groq pin revalidated; free-tier conditions not represented as permanent production pricing.
- [ ] Baseline tests, Ruff and Pyright pass.
- [ ] EvidenceBundle v1 and deterministic outputs unchanged.
- [ ] PIR complete, ADR-034 consolidated, cross-references consistent.
- [ ] Human closure sign-off recorded.

## 6. Approval record
| Artifact | Status |
|---|---|
| Overall Phase 3 plan | Pending approval |
| `001_llm_gateway` SDD | Draft; clarification gate open |
| `002_provider_resilience` SDD | Draft; clarification gate open |
| Execution plan | Draft; approval pending |
| Implementation authorization | Not granted |
