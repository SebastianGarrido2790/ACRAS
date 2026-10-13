# ACRAS — Phase 3 Implementation Plan & Decisions

**Phase:** 3 — LLM Gateway & Provider Resilience  
**Document status:** Draft for human review; no decisions in this document are approved by virtue of being written here  
**Intended repository location:** `reports/docs/phases/phase_3/implementation_plan.md`  
**Authority:** Phase-specific actionable design under the PRD, accepted ADRs in `reports/docs/architecture/system_design.md` §6, standing invariants in `README.md`  
**Baseline verification:** Reported live by the project operator immediately before this draft; this document does not independently re-run the repository checks

> **Approval rule:** Recommendations below are proposals. Decisions marked **Human approval required** remain open until explicitly accepted. Implementation must not begin for a decision-dependent feature until its material decisions and the relevant execution stage are approved. If repository evidence contradicts this document, stop and reconcile it rather than silently overriding the repository or an accepted ADR.

---

## 1. Phase Context

### 1.1 Purpose

Implement the smallest reliable LLM gateway that supports the planned Phase 4 Tier 3 personas while preserving the deterministic Tier 1–2 system. Phase 3 provides provider abstraction, bounded failure handling, automatic primary-to-fallback routing, and enough operational evidence to demonstrate and audit failover. It does **not** implement the personas, executive report orchestration, dashboard, or Phase 5 evaluation framework.

### 1.2 Business and system outcome

For an eligible LLM request, ACRAS should use the configured primary provider when healthy and automatically attempt the configured fallback when the primary fails or times out. A failure of both providers must produce a controlled, typed outcome—not an unhandled exception—and a useful audit event. The gateway must not change PD, rating, Monte Carlo outputs, or other deterministic Tier 1–2 calculations.

### 1.3 Verified starting state

The following baseline was reported as freshly verified against the repository:

- Phase 2 exit and PIR are closed: `reports/docs/phases/phase_2/implementation_plan.md` §6 has 9/9 rows populated, no `_pending_` markers, all marked satisfied; Phase 2 empirical gates were met.
- `src/schemas/evidence_bundle.py` exposes schema versions `pre-v0-draft`, `v0`, and `v1`. The v1 validators enforce finite PD, valid rating, non-null PD band, and non-empty finite ratios. `persona_verdicts=None` is valid. No v2 fields exist; Phase 4 owns those changes.
- `PersonaVerdict` has bounded persona/recommendation/lean/confidence fields and a minimum rationale length. Its recommendation enum includes `approve`, `conditional`, and `reject`.
- `params.yaml` already holds deterministic model, preprocessing, calibration, promotion-gate, simulation, and rating-threshold configuration; no gateway configuration exists.
- There is no provider integration, gateway implementation, breaker dependency, provider-outage fixture, or LLM-specific observability infrastructure. `src/gateway/` is currently only a package initializer.
- Runtime logging uses the standard library and a rotating file handler; MLflow is confined to training pipelines. Serving does not depend on MLflow. `httpx` is present only in development dependencies.
- Baseline quality checks reported: `uv run pytest` — 81 passed, 3 skipped; Ruff clean; Pyright 0 errors. The three skips were reported as pre-existing container-related skips.

### 1.4 Scope boundaries

**In scope**

1. Provider-neutral gateway request/response and error contracts.
2. Gemini primary and Hugging Face Inference API fallback, with the exact fallback model pinned only after verification and approval.
3. Timeouts, bounded retry policy (if any), per-provider circuit-breaker behavior, fallback routing, and controlled dual-provider failure.
4. Configuration for provider/model identifiers and resilience limits; secrets supplied outside version-controlled configuration.
5. Minimal provider event/cost/latency logging sufficient for Phase 3 acceptance and troubleshooting.
6. Mocked outage, timeout, recovery, malformed-response, and dual-failure tests.
7. Integration boundary checks that preserve deterministic tiers and the EvidenceBundle contract.

**Out of scope**

- Tier 3 persona implementations and persona-specific prompts/rubrics (Phase 4).
- Adding `EvidenceBundle` v2 fields or changing its current schema version (Phase 4, governed by ADR-016 and schema evolution rules).
- Deterministic divergence scoring and human-in-the-loop convergence workflow (Phase 4).
- Golden-set evaluation, calibration/divergence release gates, and broader evaluation governance (Phase 5), except for gateway-focused regression tests needed here.
- Dashboard/UI, distributed tracing platform, Prometheus, OpenTelemetry, or a general observability platform.
- Unrelated DVC dependency cleanup (including the `dvc[s3]` extra); retain as a separate non-blocking issue.

### 1.5 Phase exit criteria

Phase 3 is complete only when evidence demonstrates all of the following:

1. A healthy primary provider succeeds through the provider-neutral gateway contract.
2. A forced primary failure or timeout automatically invokes the configured fallback without an unhandled exception.
3. Both-provider failure returns a controlled, typed failure outcome; callers do not receive provider SDK/HTTP exceptions as the gateway contract.
4. Circuit-breaker transitions and fallback behavior are bounded, deterministic under test, and covered by tests.
5. Events record provider/model selection, outcome, latency, fallback/breaker transitions, and usage/cost when trustworthy provider usage data is available; sensitive content and credentials are excluded.
6. The configured fallback model is pinned and its endpoint, access, response shape, and operational availability are verified at implementation time.
7. Existing deterministic Tier 1–2 behavior and the current EvidenceBundle v1 contract remain unchanged; the baseline test suite and static checks pass.
8. The Phase 3 PIR is completed, accepted ADRs are consolidated in `system_design.md` §6, and all exit criteria have evidence links or exact test references.

---

## 2. Current State Audit and Gap Register

| ID | Verified gap | Phase 3 response | Exit evidence |
|---|---|---|---|
| G1 | No gateway substrate, provider adapter, breaker dependency, or gateway config | Add the smallest provider-neutral gateway and explicitly configured provider adapters; verify and pin the fallback model | Contract tests; config validation; primary/fallback integration tests |
| G2 | No LLM-specific event/cost schema or trace-event sink | Add a minimal structured provider-event schema and emit through existing standard-library logging; no new observability platform | Captured log assertions for success, timeout, fallback, breaker transition, dual failure, and usage/cost availability |
| G3 | Breaker thresholds exist only as ADR prose; no consumer yet | Decide and configure explicit timeouts/breaker limits before implementation; keep values configurable and bounded | Config tests plus deterministic breaker-state tests |
| G4 | No provider-outage fixture; `httpx` exists only in dev dependencies | Use mocked HTTP transport/provider adapters for deterministic fault injection; decide whether `httpx` becomes a runtime dependency with the transport choice | No live provider calls in unit tests; forced outage and recovery scenarios run in CI |
| G5 | `dvc[s3]` extra remains despite local-remote decision | Leave untouched; unrelated and non-blocking | No Phase 3 change to DVC dependency declaration |

**Risk note:** A provider fallback is an availability mechanism, not proof of semantic equivalence. The gateway can normalize transport and response contracts, but Phase 4/5 must assess persona-level quality, grounding, and cross-provider behavioral differences.

---

## 3. Requirements and Governing Constraints

### 3.1 Requirements mapped to design

| Requirement / constraint | Design consequence |
|---|---|
| PRD FR10: fallback through breaker on failure/timeout | The gateway owns bounded failure detection and automatic fallback; callers do not implement provider failover themselves |
| PRD FR9 / Phase 3 exit: logged and observable | Every request attempt and routing outcome emits a structured, redacted event; training-side MLflow is not reused as serving telemetry |
| NFR: reliability under simulated outage | Provider transport must be injectable/mockable; tests force timeout, HTTP/provider errors, malformed responses, breaker-open state, and dual failure |
| NFR: <$0.15/report | Capture provider-reported token/usage data and compute cost only from an explicit versioned rate configuration; unknown usage/cost must remain unknown, not be reported as zero |
| NFR: p50 <2 minutes/report | Use bounded attempts and explicit per-attempt timeouts; Phase 3 records per-call latency, while report-level p50 is validated when the consumer exists |
| INV-1 / ADR-001 | No LLM output enters deterministic Tier 1–2 calculations |
| INV-2 / ADR-002; ADR-014 / ADR-032 | The current EvidenceBundle v1 remains the only tier-boundary evidence object; gateway responses are not a side channel into deterministic calculations |
| ADR-006 / ADR-009 | Custom gateway with circuit breaker; Gemini primary and HF Inference API fallback; exact HF model still requires verification and pinning |
| ADR-003 / INV-3, FR12/FR13 | Phase 3 must not claim to implement Phase 5 calibration/divergence release gates; keep the gateway testable by those future gates |
| ADR-004/005/008 and INV-4/5/8 | Phase 3 prepares provider infrastructure only; persona diversity must come from domain rubrics, not random sampling, and remains Phase 4 work |
| Existing harness and standards | Pydantic contracts, deterministic validation, least complexity, evidence-based gates, explicit human approval for material decisions |

### 3.2 Non-negotiable design invariants

1. The gateway is a Tier 3 infrastructure boundary; it cannot invoke or mutate Tier 1–2 deterministic calculations.
2. Provider responses are untrusted input. Parse into a provider-neutral typed result and validate required structure before returning success.
3. No raw provider exception, raw credential, authorization header, or full sensitive prompt/response is written to logs.
4. Provider/model, timeout, breaker, retry, and cost configuration must be explicit and validated. Secrets must not be committed in `params.yaml` or source.
5. A failed fallback is a controlled failure; do not silently fabricate a persona verdict or reuse stale output.
6. Configuration and event schemas must support tests without network access or live credentials.
7. Only accepted decisions become implementation authority. Recommendations in this draft remain proposals until approved.

---

## 4. Candidate Feature Register

Keep the feature count small and organized around independently testable behavior. These are candidate features, not approval to implement.

| Feature | Purpose and boundary | Depends on | Recommendation |
|---|---|---|---|
| `001-llm-gateway` | Provider-neutral request/result/error contracts, provider adapters, configuration, response validation | Approved transport/provider strategy and model pin | Keep as the core feature |
| `002-provider-resilience` | Timeouts, bounded attempt policy, per-provider circuit breakers, fallback eligibility/routing, recovery | `001-llm-gateway` contract | Separate because failure-state behavior has distinct gates and tests |
| `003-provider-observability` | Structured redacted events for attempts, latency, provider/model, fallback, breaker transitions, usage/cost | Gateway and resilience events | Keep only if it remains a small event schema plus standard-library log sink; merge into `001`/`002` if a separate feature creates unnecessary ceremony |

**Feature-level SDD:** Prepare `spec.md`, `plan.md`, and `tasks.md` only for approved substantial features. The intended SDD directory convention must be confirmed against repository conventions before creating feature directories. Do not create a new `reports/docs/features/...` hierarchy solely on the basis of this draft.

---

## 5. Decision Log and Decisions

### Decision status vocabulary

- **Open — human approval required:** no implementation until explicitly approved.
- **Recommended, pending approval:** preferred option is proposed but not binding.
- **Fixed by existing authority:** one option is required by an accepted ADR, invariant, or existing standard; record it for traceability, not as a false choice.
- **Deferred:** belongs to a later phase or depends on evidence not yet available.

### Decision index

| ID | Question | Status | Material? |
|---|---|---|---|
| D3-01 | What provider transport/adapter approach minimizes complexity while supporting reliable, testable failover? | ✅ **Approved — Option B** (2026-10-11) | Yes |
| D3-02 | Which exact fallback model/route is pinned? | ✅ **Approved — Option C + Groq-direct** (R1/HF exhausted at $0; Llama 3.1 8B on Groq free tier to verify; pin pending evidence, 2026-10-12; new ADR required at consolidation) | Yes |
| D3-03 | What timeout, retry, breaker, and fallback policy bounds latency and cost? | ✅ **Approved — Option B with proposed values** (2026-10-11) | Yes |
| D3-04 | What is the minimum sufficient event/cost logging design for auditability? | ✅ **Approved — Option B** (2026-10-11) | Yes |
| D3-05 | What gateway contract and failure semantics are allowed across provider boundaries? | Fixed by existing authority, details below | No independent choice on core guarantees |
| D3-06 | How should gateway reliability and acceptance be tested? | Fixed by requirements; thresholds/passing evidence must be approved with execution plan | No architecture fork |

---

### D3-01 — Provider transport and adapter strategy

**Question:** Should the gateway use provider SDKs, or use a shared HTTP transport with thin provider-specific adapters?

**Context:** There are no existing provider integrations. A custom gateway is required by ADR-009. `httpx` is currently a development dependency and is available for mocked transport testing, but is not used by runtime code. The phase needs only two provider integrations and should avoid a framework-sized abstraction layer.

**Governing constraints:** ADR-006/009; Pydantic contracts; deterministic tests; minimal dependencies; bounded failure behavior; no Tier 1–2 coupling.

**Option A — Provider SDK per vendor**
- Advantages: vendor request/response types and SDK conventions; potentially less hand-written protocol parsing.
- Trade-offs: additional runtime dependencies, provider-specific behavior, and a more complex test surface; SDK retry behavior must be audited to avoid hidden retries or unbounded latency.
- Fit: reasonable if a required provider capability cannot be safely implemented via its documented HTTP API.

**Option B — Shared `httpx` transport with thin Gemini and HF adapters**
- Advantages: one injectable transport, straightforward mock-transport tests, explicit timeouts and retry ownership, smaller dependency surface than two SDKs, and consistent normalized errors.
- Trade-offs: the project owns request serialization, response parsing, and compatibility tests against each provider's documented API; malformed or changed provider responses must fail closed.
- Fit: best match for the current two-provider scope and existing test needs.

**Recommendation:** Option B. Promote `httpx` to a runtime dependency only if the approved implementation uses it; keep vendor-specific HTTP and parsing logic isolated in adapters behind one gateway contract. Do not add LangChain, LiteLLM, or a multi-provider orchestration framework for this phase.

**Approval:** ✅ **Granted — Option B approved 2026-10-11.**  
**Decision:** ☑ Option B approved  ☐ Option A  ☐ Revision requested  
**Consequences (now active):** Define a transport interface and provider adapters; disable hidden adapter retries; use mock transport for deterministic tests.  
**Parent / nested decisions:** D3-02 (fallback model pin) depends on this decision but is independently material because provider availability and response behavior must be verified.

---

### D3-02 — Exact Hugging Face fallback model pin

**Question:** Which exact model identifier should be pinned for the HF Inference API fallback?

**Context:** ADR-009 names `Llama-3.1-8B-Instruct` and `Mistral-7B-Instruct-v0.3` as candidates but explicitly leaves the exact model unpinned. Current availability, endpoint support, response schema, access requirements, latency, and cost have not been established by the supplied baseline. A model name alone is not sufficient evidence of endpoint availability or a stable deployment target.

**Governing constraints:** ADR-009; FR10; <$0.15/report; p50 <2 minutes/report; provider-neutral gateway contract; no assumption of semantic equivalence with Gemini.

**Option A — Pin a Llama 3.1 8B Instruct model endpoint**
- Advantages: matches one of the existing ADR candidates and may offer suitable instruction-following quality for structured verdict generation.
- Trade-offs: exact repository/endpoint availability, current Inference API support, rate limits, output format, and usage metering must be verified; no claim about current availability is made here.

**Option B — Pin a Mistral 7B Instruct v0.3 model endpoint**
- Advantages: also matches the ADR candidate set and may provide a lower-footprint fallback.
- Trade-offs: exact endpoint availability, response behavior, reliability, cost, and schema compliance require the same verification; no claim about current availability is made here.

**Option C — Keep the fallback model unresolved until a short, evidence-based qualification test**
- Advantages: avoids making a material provider/model decision from stale assumptions; compares only the existing ADR candidates against required operational checks.
- Trade-offs: the implementation plan cannot be considered fully approved for provider integration until the test selects a model; qualification adds a small pre-implementation task.

**Recommendation:** Option C as the decision process, then approve A or B based on a small qualification record. Verify the exact model ID and endpoint at implementation time; test authentication, successful completion, malformed/empty response behavior, timeout/failure behavior, latency, usage metadata, and cost-estimation feasibility. Record the exact model ID in version-controlled non-secret configuration only after verification. If neither candidate passes, stop and request a new decision rather than silently substituting another model.

**Approval:** ✅ **Granted — Option C (qualification process) approved 2026-10-11.** Final model selection (A or B) remains open until qualification evidence exists; do not mark the model pin approved until that evidence identifies the exact model ID.  
**Decision:** ☑ Qualification process approved  ☐ Candidate selected after evidence (pending)  ☐ Different candidate set requested  
**Acceptance evidence:** exact endpoint/model identifier; successful controlled request; normalized response contract; failure-mode test; measured latency; known/unknown usage and cost behavior; source/date of provider verification.

**Route resolution — Step 1 of qualification (recorded 2026-10-11 from live provider documentation; ✅ R1 route approved 2026-10-11, no model selected):**

ADR-009's "Hugging Face Inference API" is ambiguous across three non-interchangeable routes. Current HF documentation distinguishes them as follows (sources: `huggingface.co/docs/inference-providers`, `huggingface_hub` InferenceClient reference, fetched 2026-10-11):

- **Route R1 — Inference Providers routed API (recommended, pending approval):** OpenAI-compatible endpoint `https://router.huggingface.co/v1/chat/completions` (or `InferenceClient` with explicit `provider=`), authenticated with a single fine-grained HF token (`HF_TOKEN`, Inference Providers permission). Supports per-call provider policy suffixes (`:fastest`, `:cheapest`, `:preferred`, or an explicit named provider). Fits approved D3-01 Option B directly: plain `httpx` POST, no new SDK dependency (`huggingface_hub` is not installed and not required). Billing via the HF account (pay-as-you-go; PRO credits).
- **Route R2 — `hf-inference` as the pinned underlying provider:** HF's own first-party serverless provider inside the R1 network (successor to the legacy Serverless Inference API). Selectable as `provider="hf-inference"` within R1. Candidate underlying pin for auditability, subject to per-model availability check in Step 2.
- **Route R3 — Dedicated Inference Endpoints (rejected for Phase 3):** managed per-model deployment with always-on cost. Disproportionate for a fallback path; out of scope.
- Also rejected: the legacy `api-inference.huggingface.co` serverless endpoint (superseded by Inference Providers) and `provider="auto"` routing (non-deterministic provider choice per call; incompatible with auditability — the underlying provider MUST be explicitly pinned in configuration).

**Approved route (2026-10-11):** R1 with an explicitly pinned underlying provider. This approves the routing architecture only: one HF credential, one transport (`httpx`, already present at 0.28.1), deterministic per-call routing, and HF-side billing/usage metadata. Qualification order: check the live provider mapping for both candidates against `hf-inference` first (HF documents it as focused mainly on CPU inference and smaller or historically important models, so 7B–8B availability MUST NOT be assumed), then run authenticated requests and collect the evidence. If neither candidate is available through the approved provider, pause for a new provider/model decision rather than silently switching routes. Exact model and final provider pin remain unresolved until the evidence is collected.

**Qualification criteria (Step 2, per candidate model on the approved route):** exact model ID + route URL + pinned provider; controlled completion through the gateway-shaped adapter (not raw SDK); response-schema parse against the gateway contract; empty/malformed-response handling; timeout and connection-failure behavior against D3-03 budgets (15s primary / 20s fallback); measured p50/latency; presence/absence of provider usage metadata and cost computability (unknown stays unknown per D3-04); auth scope used. Sanitized report only: no prompts, responses, tokens, or credentials recorded.

**Step-2 prerequisites (not yet met):** no `HF_TOKEN`/`HUGGINGFACEHUB_API_TOKEN` present in this environment (existence checked 2026-10-11, values never read); operator must supply a fine-grained token out-of-band before controlled requests. `huggingface_hub` deliberately not added (D3-01 B uses raw `httpx`).

**Step-2 outcome (executed 2026-10-11, operator-run, 4 bounded calls, sanitized metadata only):**

- Live provider mapping (`GET router.huggingface.co/v1/models`, 127 entries, all with provider data): `meta-llama/Llama-3.1-8B-Instruct` live on novita / nscale / featherless-ai / deepinfra — `hf-inference` absent. `mistralai/Mistral-7B-Instruct-v0.3` absent from the routed listing entirely. Zero of 127 entries list `hf-inference` as a live provider.
- Controlled requests (`POST router.huggingface.co/v1/chat/completions`, `hf-inference` pin, fine-grained operator token): valid-minimal → HTTP 400 for **both** candidates (329.6ms Llama, 166.4ms Mistral — router-level rejection, auth accepted since no 401); malformed-empty-messages → HTTP 400 both. No completion, usage, or latency-vs-budget evidence obtainable on this pin.
- **Finding:** neither candidate is servable through the approved `hf-inference` pin. This triggers the approved pause-condition — no silent route switch.

**Step-3 recommendation (proposal, not approved; new human decision required):** qualify `meta-llama/Llama-3.1-8B-Instruct` on an explicitly pinned third-party provider (novita or deepinfra: live per mapping, listed $0.02–0.06/M in / $0.05–0.06/M out — two orders of magnitude inside the <$0.15/report ceiling; billing stays HF-side under the single-token model, so R1 architecture is unchanged). Open items for that run: gated-repo license acceptance for the operator's account, then valid/malformed/latency/usage legs. `mistralai/Mistral-7B-Instruct-v0.3` cannot proceed on the routed API in its current form — either drop it from the candidate set or replace it by separate decision. Exact model + final provider pin remain unselected until that evidence exists.

**Provider decision (approved 2026-10-11):** qualify `meta-llama/Llama-3.1-8B-Instruct` pinned to `novita` (lowest listed first-token latency, 490.6ms). Mistral-v0.3 fate still open — decided separately before any final pin. Model pin itself remains unselected pending this run's evidence.

**Novita-leg outcome (executed 2026-10-11/12, operator-run, bounded sanitized calls):** first run → HTTP 402 (no HF-side billing); after custom Novita key configured → HTTP 403 uniform; auth confusion resolved via `whoami-v2` (dead token string regenerated; fresh token returns 200) plus Meta gated-repo license acceptance (ACCEPTED) and gated-repo-read token scope. Final error body: `{"code":403,"reason":"NOT_ENOUGH_BALANCE","message":"not enough balance"}` — the Novita key carries no usable credit, so rejection is provider-side balance, not model, license, scope, or credential validity. No completion/usage/latency evidence obtainable on this key. Error-taxonomy notes for D3-05: billing failure surfaces as 402 regardless of payload; provider-balance failure surfaces as 403 with a machine-readable `reason` field — adapter must classify `NOT_ENOUGH_BALANCE` as fallback-eligible provider failure, not auth error. ** pivot (no new architecture decision; operator action):** retry the identical probe with a funded custom key — DeepInfra free trial credit first (Llama-3.1-8B live on deepinfra per mapping); else Novita top-up. Selections unchanged: route R1 approved, novita-first order approved, model pin unselected. If no $0-funded key materializes, escalate to a fallback-funding decision (PRO, top-up, or local-endpoint D-change) rather than weakening qualification.

**Novita card-wall (2026-10-12, operator-confirmed):** the $101 voucher and any top-up require a credit card the operator does not hold — Novita path closed at $0.

**Cerebras/DeepInfra dead-ends (2026-10-12, operator screenshots):** Cerebras signup gates on payment ("Add credits to get started"; pay-or-limited-credits choice); DeepInfra pricing page shows pay-per-use with no claimable free credit — both closed at $0 without a card.

**Groq-direct decision (approved 2026-10-12):** fallback moves to **Groq Cloud direct**, OpenAI-compatible endpoint `https://api.groq.com/openai/v1`, free-tier API key (no card per third-party reports — verify at signup), Llama 3.1 8B family as the candidate. What survives unchanged: approved D3-01 Option B transport (`httpx` + OpenAI-compatible contract — Groq is OpenAI-compatible, so adapter shape, error taxonomy, and test matrix stand). What changes and needs explicit handling:
- **Route designation:** exits the approved R1/HF-router designation. This conflicts with ADR-009's HF fallback designation as written — a **new ADR superseding the fallback designation is required at Phase 3 consolidation** (§7 step 6); it is recorded here now as a known pending ADR impact, not implemented silently. The R1/HF findings above are retained verbatim for traceability.
- **Model ID form:** Groq uses its own IDs (e.g. `llama-3.1-8b-instant`). Caution from live Groq docs (fetched 2026-10-12): `llama-3.1-8b-instant` is currently tagged **Enterprise / ContactSales**, with priced production models listed as GPT-OSS and others — free-tier servability of the Llama 3.1 8B ID is **unverified** and MUST be established before any completion legs.
- **Auth:** `GROQ_API_KEY` from Groq console, same secret discipline as `HF_TOKEN` (session env only, never chat/repo); `HF_TOKEN`/Novita key no longer needed for this leg.
- **Qualification order:** (0) authenticated `GET /v1/models` — confirm which IDs this free key can actually serve; (1) valid-minimal + malformed legs against the confirmed ID; (2) latency vs D3-03 budgets; (3) usage/cost metadata (free-tier accounting). Stop and request a new decision if the Llama ID is not servable on the free tier.
- Mistral-v0.3 fate still open; model pin remains unselected until Groq-leg evidence exists.

---

### D3-03 — Resilience policy: timeouts, retries, breakers, and fallback

**Question:** What failure policy provides automatic failover without retry storms, excessive latency, or duplicate cost?

**Context:** FR10 requires fallback on failure/timeout. ADR-006/009 requires a custom gateway with a circuit breaker, but exact values are not yet configured. The report-level p50 target is under two minutes and the per-report cost target is below $0.15. Phase 3 has no Tier 3 consumer yet, so this policy must be independently testable.

**Option A — Retry the primary several times before fallback**
- Advantages: may recover from transient provider faults without changing providers.
- Trade-offs: increases tail latency and can duplicate billable requests; hidden SDK retries could multiply attempts; can delay fallback during an outage.

**Option B — One bounded primary attempt, then fallback on eligible failure/timeout; independent breaker state per provider**
- Advantages: predictable latency/cost; simple fault-injection tests; a failing primary does not poison the fallback's breaker state; matches FR10 directly.
- Trade-offs: transient primary failures immediately use the fallback; a fallback request may still fail independently.

**Option C — Retry once on narrowly defined transient transport failures, then fallback**
- Advantages: may recover from short-lived network errors.
- Trade-offs: more branches and cost/latency; needs clear idempotency and error classification; little value unless measured evidence supports it.

**Recommendation:** Option B for the first implementation. Do not add same-provider retries unless qualification tests or observed evidence show a material benefit. Treat provider timeout, connection failure, retryable server failure, and breaker-open state as fallback-eligible. Treat invalid local configuration, missing credentials, invalid gateway input, and response-schema violations according to explicit policy: never retry a deterministic local validation error; response/schema failures should be logged and surfaced as controlled provider failure, with fallback behavior explicitly tested.

**Initial values (accepted 2026-10-11 as test starting points, subject to qualification evidence):**

| Setting | Proposed starting value | Rationale / qualification |
|---|---:|---|
| Primary request timeout | 15 seconds | Bounds time spent on an unresponsive primary; validate against real provider latency |
| Fallback request timeout | 20 seconds | Allows a separate bounded attempt while preserving a practical end-to-end budget |
| Same-provider retries | 0 | Prevents retry amplification and duplicated cost in the initial design |
| Breaker failure threshold | 3 consecutive eligible failures per provider | Simple, testable threshold; keep configurable |
| Breaker reset/open interval | 30 seconds | Enables recovery probe without waiting indefinitely; keep configurable |
| Half-open probes | 1 request per provider | Limits concurrent recovery traffic; verify implementation semantics |
| Max provider attempts per gateway call | 2 total (one primary + one fallback) | Explicit upper bound on attempts and cost |

These are engineering starting points, not facts derived from existing repository configuration. The implementation stage must verify the selected `pybreaker` version's actual transition semantics and tests must lock down behavior. If the provider qualification shows these values cannot meet the PRD latency/cost constraints, return for approval rather than silently changing the policy.

**Approval:** ✅ **Granted — Option B with proposed values approved 2026-10-11** (values stand as test starting points, subject to qualification evidence).  
**Decision:** ☑ Option B and proposed values approved  ☐ Option B with revised values  ☐ Another option  
**Consequences (now active):** Put values in a validated gateway configuration section; define eligible failure categories; use separate breaker instances per provider; prove open/half-open/closed transitions and bounded attempt count in tests.

---

### D3-04 — Minimal provider observability and cost evidence

**Question:** What is the minimum logging design that satisfies Phase 3 auditability and cost visibility without introducing an observability platform?

**Context:** Existing standard-library rotating logs are available, but there is no LLM event schema, token/cost metering, trace-event plumbing, OpenTelemetry, or Prometheus. PRD FR9 and the Phase 3 exit criterion require logged/observable failover. MLflow is training-side and must remain outside serving.

**Option A — Add an observability platform now (e.g., OpenTelemetry/metrics backend)**
- Advantages: richer traces, metrics, and future operational integrations.
- Trade-offs: disproportionate infrastructure and dependency complexity for a two-provider gateway; not required by Phase 3's stated acceptance criteria.

**Option B — Define a minimal structured event schema and emit through existing standard-library logging**
- Advantages: smallest implementation that is testable in CI and produces auditable evidence; avoids a new runtime service or platform.
- Trade-offs: no distributed tracing UI or production metrics dashboard; future migration may be needed if operational requirements expand.

**Option C — Log only free-form messages**
- Advantages: lowest initial coding effort.
- Trade-offs: brittle tests and weak machine-readable auditability; does not reliably support cost/fallback analysis.

**Recommendation:** Option B. Use a versioned `ProviderEvent`-style schema (exact class/name may follow repository naming conventions) with fields sufficient to record: timestamp, request/correlation ID, provider, model ID, attempt number, outcome/category, latency, fallback-used flag, breaker state/transition, provider-reported usage when available, estimated cost when computable, and sanitized error category. Emit structured key/value or JSON-compatible fields through the existing logging path. Do not log prompts/responses by default, secrets, authorization headers, or personally/financially sensitive payloads. If the provider omits usage metadata or a trusted rate is unavailable, record usage/cost as unknown—not zero. Store pricing assumptions as explicit versioned configuration and document their source/date; do not hard-code unexplained prices into business logic.

**Approval:** ✅ **Granted — Option B approved 2026-10-11** (minimal approach and proposed event fields).  
**Decision:** ☑ Option B approved  ☐ Option A  ☐ Revision requested  
**Consequences (now active):** No OTel/Prometheus rollout in Phase 3; event schema and redaction tests are part of `003-provider-observability` or merged equivalent. Report-level cost acceptance remains provisional until a report-producing consumer exists; Phase 3 must demonstrate auditable per-call usage/cost evidence where supported.

---

### D3-05 — Gateway contract and failure semantics

**Question:** What may cross the gateway boundary, and how are provider failures exposed to future Tier 3 callers?

**Status:** **Fixed by existing authority** for the core constraints; exact type names and field layout follow existing project standards and should be finalized in the feature SDD.

**Required design:**

- Expose a provider-neutral, Pydantic-validated request/result contract. Provider adapters must not leak raw SDK/HTTP response objects to callers.
- Normalize provider failures into a small typed error taxonomy (for example: timeout, connection/provider unavailable, rate-limited, server error, invalid provider response, configuration/authentication error, and breaker open). Final enum names should be chosen once in the SDD, not expanded speculatively.
- Return success only after response parsing and required structural validation. A response that cannot be parsed or violates the gateway contract is not success.
- If both providers fail, return/raise one documented gateway-level failure with sanitized causal metadata and an event ID. Never fabricate a successful result or silently use stale output.
- Keep gateway output distinct from `EvidenceBundle` and `PersonaVerdict` unless a later approved feature explicitly defines the conversion boundary. Phase 3 does not add EvidenceBundle v2 fields.
- Do not pass LLM output into deterministic PD, rating, simulation, or ratio calculations.

**Why there are no competing options:** Returning provider-native objects or allowing LLM output to influence deterministic calculations conflicts with accepted ADRs/invariants. Those are not viable design alternatives. The SDD may refine field names and exact exception/result representation without reopening the architectural constraint.

**Approval:** No separate architecture choice is required. Human review of the concrete contract is required as part of approving the `001-llm-gateway` SDD.

---

### D3-06 — Reliability tests and acceptance evidence

**Question:** How will Phase 3 prove failover and controlled failure without relying on live provider availability in CI?

**Status:** **Fixed by requirements** that outage behavior is demonstrated and automated; the exact test organization can follow repository conventions.

**Required test scenarios:**

1. Primary succeeds; fallback is not called.
2. Primary returns eligible server/provider failure; fallback succeeds.
3. Primary times out; fallback succeeds.
4. Primary breaker is open; gateway routes directly to fallback within the configured attempt budget.
5. Fallback fails after primary failure; gateway returns a controlled failure and emits both attempt outcomes.
6. Provider response is malformed, empty, or fails schema validation; no invalid success is returned.
7. Breaker opens at the configured threshold, rejects or routes requests while open, and permits a bounded half-open probe after reset.
8. Recovery closes the breaker according to the pinned library's actual behavior.
9. Configuration validation rejects invalid timeout/threshold/model settings and never exposes secret values in errors/logs.
10. Event tests assert provider, model, latency, fallback, breaker outcome, usage/cost-known state, and redaction behavior.
11. Existing Phase 0–2 tests, Ruff, and Pyright remain clean.

**Test method:** Mock the transport/provider boundary; unit and integration tests must not require live network access or real credentials. A small, explicitly controlled manual qualification against each real provider may be needed to pin model availability and verify current API behavior, but it must not become a flaky CI dependency.

**Acceptance gate:** All required deterministic tests pass; forced primary failure triggers fallback; dual failure is controlled; logs prove the route taken; deterministic-tier regression checks pass. Exact file/test references are recorded in the execution plan and PIR.

---

## 6. Proposed Implementation Shape (conditional on approval)

This section summarizes the recommended go-to design; it is not implementation authorization.

1. **Configuration:** Add a validated gateway section to `params.yaml` for provider identifiers/model IDs and non-secret resilience/cost settings. Resolve credentials through the project's approved secret/environment mechanism. Do not put secrets in YAML.
2. **Gateway core:** A small provider-neutral service owns attempt limits, timeout policy, fallback routing, breaker consultation, normalized errors, and event emission. Keep business/persona logic out of it.
3. **Provider adapters:** Thin Gemini and HF Inference API adapters implement the same internal contract using the approved transport strategy. Keep provider-specific URLs, headers, payload shapes, and response parsing inside the adapter boundary.
4. **Resilience:** Use the accepted `pybreaker` direction, subject to dependency/version verification. Maintain independent breaker state per provider. No unbounded loops and no hidden SDK retry behavior.
5. **Validation:** Parse provider output into a typed result, validate required fields/shape, and classify malformed output as a controlled provider failure. The future persona schema is Phase 4; do not prematurely change `PersonaVerdict` or EvidenceBundle v1 in Phase 3.
6. **Events:** Emit redacted structured events through existing logging. Make event creation independently testable; never make successful gateway operation depend on a new telemetry backend.
7. **Tests:** Inject transport/adapters and breaker clock/state as needed for deterministic fault tests. Keep live provider checks separate from ordinary CI.

### Integration boundary warning

The current architecture diagram reportedly includes agents that call Tier 1 and calculate financial ratios, while Phase 2 already provides PD/rating/ratio outputs. Phase 3 must not duplicate those deterministic responsibilities. The eventual Phase 4 consumer should receive the existing validated EvidenceBundle v1 as its evidence input, subject to the accepted architecture and the Phase 4 plan. Resolve any diagram/document inconsistency before Phase 4 integration; do not expand Phase 3 to rewrite Tier 1–2.

---

## 7. What Happens After Approval

1. Record explicit decisions for D3-01, D3-02 qualification process, D3-03, and D3-04; leave D3-02 model selection open until exact provider evidence exists.
2. Create `reports/docs/phases/phase_3/implementation_plan.md` only after this draft is reviewed and approved; maintain the repository's established phase-plan format.
3. Create the Phase 3 `execution_plan.md` from the approved decisions, with staged dependencies and evidence gates. No stage may depend on an unresolved material decision.
4. Confirm the repository's existing feature-SDD path convention before creating feature directories. Create only the SDDs needed for the approved substantial features.
5. Implement one approved execution stage at a time. Stop if actual repository evidence changes the decision basis or if a material architecture/scope/cost/security trade-off emerges.
6. Update accepted ADRs in `reports/docs/architecture/system_design.md` §6 only after the corresponding decision is approved and the implementation evidence supports it. Do not treat this phase plan as a second ADR source of truth.

---

## 8. Post-Implementation Review & Remediation (leave open until Phase 3 is executed)

| Review question | Evidence to record | Status |
|---|---|---|
| Did primary success and automatic fallback meet the approved policy? | Test names/results and controlled qualification evidence | `_pending_` |
| Were latency and max-attempt bounds respected under forced faults? | Test results and measured per-attempt latency | `_pending_` |
| Was breaker behavior consistent with the pinned `pybreaker` version? | Version pin and transition tests | `_pending_` |
| Were provider events useful, complete, and redacted? | Captured event assertions and redaction tests | `_pending_` |
| Was usage/cost measured accurately where possible and marked unknown otherwise? | Provider usage evidence, rate-source/date, cost tests | `_pending_` |
| Did the phase preserve EvidenceBundle v1 and deterministic Tier 1–2 outputs? | Regression suite and schema diff | `_pending_` |
| What diverged from the approved plan, and why? | Actual-vs-planned analysis; accepted deviations and owner | `_pending_` |
| What remediation remains, with priority and phase ownership? | Explicit issue/ADR/PIR references | `_pending_` |

Do not replace `_pending_` markers with success labels until evidence is available. Any unresolved issue must be classified as blocking, accepted risk with rationale/owner, or deferred to a named later phase.

---

## 9. Phase Closure

Phase 3 can be closed only after:

- [ ] Human-approved material decisions are reflected in the execution plan and applicable SDDs.
- [ ] The exact fallback model is verified and pinned, or the phase is explicitly blocked pending an approved alternative.
- [ ] Primary success, automatic fallback, breaker behavior, recovery, malformed output, and dual-provider failure are covered by deterministic tests.
- [ ] Events demonstrate route selection, failure/fallback, latency, breaker behavior, and usage/cost-known status without leaking secrets or sensitive content.
- [ ] Existing 81-pass / 3-skip baseline is reconciled against post-change test results; Ruff and Pyright remain clean, with any change explained.
- [ ] EvidenceBundle v1 and Tier 1–2 deterministic behavior remain unchanged.
- [ ] ADR updates are consolidated in `reports/docs/architecture/system_design.md` §6; no competing ADR source is created.
- [ ] PIR rows are completed with evidence; no `_pending_` remains unless a formally accepted exception is recorded.
- [ ] The Phase 3 exit criteria are explicitly marked satisfied or not satisfied with reasons.

**Closure status:** Not started.  
**Human sign-off:** Pending.  
**Next phase:** Phase 4 may begin only after Phase 3 exit criteria are satisfied and the Phase 4 schema/persona design is separately planned and approved.

---

## 10. Human Decision Record

Please record approval explicitly; silence is not approval.

| Decision | Approved choice / changes requested | Approver decision | Date |
|---|---|---|---|
| D3-01 Transport and adapters | Approved Option B | Approved | 2026-10-11 |
| D3-02 Fallback-model qualification and final pin | R1/HF exhausted ($0); Groq-direct approved, Llama 3.1 8B free-tier servability to verify; pin pending | Approved (Groq route + process; pin pending; new ADR at consolidation) | 2026-10-12 |
| D3-03 Resilience policy and proposed initial values | Approved Option B with proposed values as starting points | Approved | 2026-10-11 |
| D3-04 Structured event and cost logging | Approved Option B | Approved | 2026-10-11 |
| D3-05 Gateway contract | Review in SDD; architectural constraints fixed | Pending SDD review |  |
| D3-06 Reliability test matrix | Include in execution plan; exact evidence references later | Pending execution-plan review |  |

**Overall phase-plan approval:** Pending.  
**Implementation authorization:** Not granted by this draft.
