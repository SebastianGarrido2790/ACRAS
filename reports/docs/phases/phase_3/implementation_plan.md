# ACRAS — Phase 3 Implementation Plan & Decisions

**Phase:** 3 — LLM Gateway & Provider Resilience  
**Document status:** ✅ Approved 2026-10-12 (all material decisions, both SDDs, and the execution plan). Implemented 2026-10-12 through execution-plan Stages 0–8; Post-Implementation Review completed and exit criteria audited 2026-10-19 (Stage 9) — see §8, §9 and §11.  
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
2. Gemini primary and Groq-direct fallback, with the fallback model pinned as `openai/gpt-oss-20b` (approved 2026-10-12; the superseding ADR was filed and consolidated as ADR-034 in `reports/docs/architecture/system_design.md` §6 on 2026-10-12).
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
| ADR-006 / ADR-009 / ADR-034 (accepted 2026-10-12) | Custom gateway with circuit breaker; Gemini primary and Groq-direct fallback pinned as `openai/gpt-oss-20b` (D3-02, 2026-10-12); ADR-034 supersedes ADR-009's HF fallback designation and leaves its custom-gateway, `pybreaker`, and Gemini-primary decisions intact |
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
| `001_llm_gateway` | Provider-neutral request/result/error contracts, provider adapters, configuration, response validation | Approved transport/provider strategy and model pin | Keep as the core feature |
| `002_provider_resilience` | Timeouts, bounded attempt policy, per-provider circuit breakers, fallback eligibility/routing, recovery | `001_llm_gateway` contract | Separate because failure-state behavior has distinct gates and tests |
| `003_provider_observability` | Structured redacted events for attempts, latency, provider/model, fallback, breaker transitions, usage/cost | Gateway and resilience events | Keep only if it remains a small event schema plus standard-library log sink; merge into `001`/`002` if a separate feature creates unnecessary ceremony |

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
| D3-02 | Which exact fallback model/route is pinned? | ✅ **Approved — `openai/gpt-oss-20b` on Groq-direct pinned 2026-10-12** (R1/HF + Llama legs exhausted with documented causes; superseding ADR-034 accepted and consolidated 2026-10-12) | Yes |
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

**Approval:** ✅ **Granted — Option B approved 2026-10-11.** (The provider set implied by this option is the one pinned in D3-02/ADR-034: Gemini primary, Groq-direct fallback; the option text's HF reference is superseded by ADR-034 and retained here only as decision history.)  
**Decision:** ☑ Option B approved  ☐ Option A  ☐ Revision requested  
**Consequences (now active):** Define a transport interface and provider adapters; disable hidden adapter retries; use mock transport for deterministic tests.  
**Parent / nested decisions:** D3-02 (fallback model pin) depends on this decision but is independently material because provider availability and response behavior must be verified.

---

### D3-02 — Exact fallback model pin (originally HF; pinned to Groq-direct `openai/gpt-oss-20b`)

**Question (as framed on 2026-10-11):** Which exact model identifier should be pinned for the fallback provider? The candidate set at that time was the HF Inference API routes.

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

**Approval:** ✅ **Granted — Option C process approved 2026-10-11; PIN APPROVED 2026-10-12: `openai/gpt-oss-20b` on Groq-direct (`https://api.groq.com/openai/v1`, free-tier `GROQ_API_KEY`).**  
**Decision:** ☑ Qualification process approved  ☑ Model pinned: `openai/gpt-oss-20b` on Groq-direct  ☐ Different candidate set requested  
**Pinned configuration (non-secret, for versioned config at implementation):** provider `groq`; route `https://api.groq.com/openai/v1`; model `openai/gpt-oss-20b`; auth via `GROQ_API_KEY` session env (never committed); free-tier rate limits apply; cost $0 with listed production rates as fallback reference (source: Groq docs + live listing, 2026-10-12).
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

**Gemini-leg outcome (executed 2026-10-12, operator-run, sanitized metadata only):** authenticated `GET /models` → 200 with 63 servable IDs; `gemini-2.0-flash` absent (retired — the approved pick cannot be fulfilled); valid-minimal legs → HTTP 404 both; malformed leg → HTTP 400 (route alive, auth accepted). **Substitute pick (approved 2026-10-12): `gemini-2.5-flash`** — GA stable, version-pinned (floating `-latest` aliases rejected as unpinnable); same qualification legs required before the Stage 2 adapter is built.

**Gemini-leg outcome (executed 2026-10-12, operator-run, 3 bounded calls, sanitized metadata only) — pin criteria satisfied:** valid-minimal ×2 → HTTP 200 at 2176.2ms / 1326.1ms wall (inside the 15s primary budget; higher baseline than the Groq leg's ~410ms — queue-dominated, still an order of magnitude inside budget); usage metadata present (`prompt_tokens`, `completion_tokens`, `total_tokens`); OpenAI response shape; `finish_reason: length` is the 8-token probe-cap artifact; malformed-empty-messages → HTTP 400 in 907.2ms. **Primary pin (APPROVED 2026-10-12): `gemini-2.5-flash` on Google's OpenAI-compatible endpoint, `GEMINI_API_KEY` auth.** Both provider pins are now evidenced; D3-02 qualification is complete. Full servable list captured from the operator shell: current stable flash IDs include `gemini-2.5-flash`, `gemini-flash-latest` (floating alias — unsuitable for pinning), and newer dated/preview families. No completion/usage/latency evidence exists for any primary model yet.

**Novita-leg outcome (executed 2026-10-11/12, operator-run, bounded sanitized calls):** first run → HTTP 402 (no HF-side billing); after custom Novita key configured → HTTP 403 uniform; auth confusion resolved via `whoami-v2` (dead token string regenerated; fresh token returns 200) plus Meta gated-repo license acceptance (ACCEPTED) and gated-repo-read token scope. Final error body: `{"code":403,"reason":"NOT_ENOUGH_BALANCE","message":"not enough balance"}` — the Novita key carries no usable credit, so rejection is provider-side balance, not model, license, scope, or credential validity. No completion/usage/latency evidence obtainable on this key. Error-taxonomy notes for D3-05: billing failure surfaces as 402 regardless of payload; provider-balance failure surfaces as 403 with a machine-readable `reason` field — adapter must classify `NOT_ENOUGH_BALANCE` as fallback-eligible provider failure, not auth error. ** pivot (no new architecture decision; operator action):** retry the identical probe with a funded custom key — DeepInfra free trial credit first (Llama-3.1-8B live on deepinfra per mapping); else Novita top-up. Selections unchanged: route R1 approved, novita-first order approved, model pin unselected. If no $0-funded key materializes, escalate to a fallback-funding decision (PRO, top-up, or local-endpoint D-change) rather than weakening qualification.

**Novita card-wall (2026-10-12, operator-confirmed):** the $101 voucher and any top-up require a credit card the operator does not hold — Novita path closed at $0.

**Cerebras/DeepInfra dead-ends (2026-10-12, operator screenshots):** Cerebras signup gates on payment ("Add credits to get started"; pay-or-limited-credits choice); DeepInfra pricing page shows pay-per-use with no claimable free credit — both closed at $0 without a card.

**Groq-direct decision (approved 2026-10-12):** fallback moves to **Groq Cloud direct**, OpenAI-compatible endpoint `https://api.groq.com/openai/v1`, free-tier API key (no card per third-party reports — verify at signup), Llama 3.1 8B family as the candidate. What survives unchanged: approved D3-01 Option B transport (`httpx` + OpenAI-compatible contract — Groq is OpenAI-compatible, so adapter shape, error taxonomy, and test matrix stand). What changes and needs explicit handling:
- **Route designation:** exits the approved R1/HF-router designation. This conflicted with ADR-009's HF fallback designation as written — a **new ADR superseding the fallback designation was required at Phase 3 consolidation** (§7 step 6); it was recorded here as a known pending ADR impact, not implemented silently. **Resolved 2026-10-12:** ADR-034 (Groq Cloud Direct as fallback) was accepted and consolidated in `reports/docs/architecture/system_design.md` §6; ADR-009's custom-gateway, `pybreaker`, and Gemini-primary decisions remain unmodified, and its body is preserved as decision history. The R1/HF findings above are retained verbatim for traceability.
- **Model ID form:** Groq uses its own IDs (e.g. `llama-3.1-8b-instant`). Caution from live Groq docs (fetched 2026-10-12): `llama-3.1-8b-instant` is currently tagged **Enterprise / ContactSales**, with priced production models listed as GPT-OSS and others — free-tier servability of the Llama 3.1 8B ID is **unverified** and MUST be established before any completion legs.
- **Auth:** `GROQ_API_KEY` from Groq console, same secret discipline as `HF_TOKEN` (session env only, never chat/repo); `HF_TOKEN`/Novita key no longer needed for this leg.
- **Qualification order:** (0) authenticated `GET /v1/models` — confirm which IDs this free key can actually serve; (1) valid-minimal + malformed legs against the confirmed ID; (2) latency vs D3-03 budgets; (3) usage/cost metadata (free-tier accounting). Stop and request a new decision if the Llama ID is not servable on the free tier.
- Mistral-v0.3 fate still open; model pin remains unselected until Groq-leg evidence exists.

**Groq model-listing outcome (2026-10-12, operator-run, authenticated `GET /v1/models` → 200):** servable IDs on this free key: `allam-2-7b`, `canopylabs/orpheus-{arabic-saudi,v1-english}`, `meta-llama/llama-prompt-guard-{2-22m,2-86m}`, `openai/gpt-oss-{120b,20b,safeguard-20b}`, `qwen/qwen3.8-27b`, `whisper-large-{v3,v3-turbo}`. **No Llama chat/instruct model is servable** — consistent with the Enterprise tag on `llama-3.1-8b-instant`. Neither ADR-009 candidate can proceed on Groq-free. Notable: `openai/gpt-oss-20b` advertises tools, `json_mode`, `structured_outputs`, and reasoning support — technically relevant to Phase 4 structured-verdict parsing. Next step requires a new candidate/route decision (see Step-3 update).

**Candidate-set decision (approved 2026-10-12):** qualify **`openai/gpt-oss-20b`** on Groq-direct as the fallback candidate (20B instruction-tuned, live on the operator's free key today, advertises tools/`json_mode`/`structured_outputs`/reasoning — the structured-output support is directly relevant to Phase 4 verdict parsing). This supersedes the Llama/Mistral shortlist for the $0 path; the HF-leg findings stay on record. Mistral-v0.3 is dropped (unservable on every verified $0 route). Model pin itself remains unselected pending this run's evidence.

**gpt-oss-20b outcome (executed 2026-10-12, operator-run, 3 bounded calls, sanitized metadata only) — all pin criteria satisfied:** valid-minimal ×2 → HTTP 200 at 410.3ms / 407.7ms wall (inference ~12ms + queue ~240–310ms; two orders of magnitude inside the 20s fallback budget); usage metadata rich (`prompt_tokens`, `completion_tokens`, `total_tokens`, per-phase times, `queue_time`, `reasoning_tokens`) — cost computable as $0 under free tier with listed production rates as fallback reference; OpenAI response shape plus Groq extras (`service_tier`, `system_fingerprint`, `usage_breakdown`, `x_groq`) — parseable into the gateway contract; `finish_reason: length` is an artifact of the 8-token probe cap, not a model limit; malformed-empty-messages → HTTP 400 in 95.9ms (controlled rejection, no invalid success). Transport note confirmed: browser-style UA required (Cloudflare 1010 otherwise) — already in D3-05.

**Pin (APPROVED 2026-10-12):** **`openai/gpt-oss-20b` on Groq-direct (`https://api.groq.com/openai/v1`, free-tier `GROQ_API_KEY`)** is the Phase 3 fallback. Sole candidate with complete positive evidence on every D3-02 acceptance item (200 ×2 at ~410ms vs 20s budget; rich usage metadata; clean 400 on malformed; OpenAI-parseable shape); all prior candidates failed with documented causes above. Next: SDDs/execution plan.

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
**Consequences (now active):** No OTel/Prometheus rollout in Phase 3; event schema and redaction tests are part of `003_provider_observability` or merged equivalent. Report-level cost acceptance remains provisional until a report-producing consumer exists; Phase 3 must demonstrate auditable per-call usage/cost evidence where supported.

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
- Transport fingerprint: the gateway HTTP client MUST present a standard browser-style `User-Agent`. Evidence (2026-10-12): Python `urllib`'s default signature received Cloudflare `error code: 1010` from `api.groq.com` on every path (including `GET /v1/models`) with valid credentials, while identical credentials via curl with a Mozilla UA returned HTTP 200 — the block was client fingerprinting, not auth. Pin the adapter's default headers and cover them with a test asserting their presence.
- Observed error-code mapping (qualification evidence, 2026-10-11/12 — classify on status **plus** machine-readable reason/body, never status alone): HF router 400 = unmapped model+provider pin or malformed payload; 401 = dead credential (verify via `whoami`-style identity check before concluding anything about the route); 402 = no billing, payload-independent; 403 with `reason: NOT_ENOUGH_BALANCE` = fallback-eligible provider failure, NOT an auth error (do not retry it as one, do not loop it); 403 without such reason after license/scope fixes = configuration error. A uniform status across valid and malformed legs indicates rejection above payload validation (billing/auth/fingerprint), not a schema problem.

**Why there are no competing options:** Returning provider-native objects or allowing LLM output to influence deterministic calculations conflicts with accepted ADRs/invariants. Those are not viable design alternatives. The SDD may refine field names and exact exception/result representation without reopening the architectural constraint.

**Approval:** No separate architecture choice is required. Human review of the concrete contract is required as part of approving the `001_llm_gateway` SDD.

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
3. **Provider adapters:** Thin Gemini and Groq adapters implement the same internal contract using the approved transport strategy. Keep provider-specific URLs, headers, payload shapes, and response parsing inside the adapter boundary.
4. **Resilience:** Use the accepted `pybreaker` direction, subject to dependency/version verification. Maintain independent breaker state per provider. No unbounded loops and no hidden SDK retry behavior.
5. **Validation:** Parse provider output into a typed result, validate required fields/shape, and classify malformed output as a controlled provider failure. The future persona schema is Phase 4; do not prematurely change `PersonaVerdict` or EvidenceBundle v1 in Phase 3.
6. **Events:** Emit redacted structured events through existing logging. Make event creation independently testable; never make successful gateway operation depend on a new telemetry backend.
7. **Tests:** Inject transport/adapters and breaker clock/state as needed for deterministic fault tests. Keep live provider checks separate from ordinary CI.

### Integration boundary warning

The current architecture diagram reportedly includes agents that call Tier 1 and calculate financial ratios, while Phase 2 already provides PD/rating/ratio outputs. Phase 3 must not duplicate those deterministic responsibilities. The eventual Phase 4 consumer should receive the existing validated EvidenceBundle v1 as its evidence input, subject to the accepted architecture and the Phase 4 plan. Resolve any diagram/document inconsistency before Phase 4 integration; do not expand Phase 3 to rewrite Tier 1–2.

---

## 7. What Happens After Approval

1. Record explicit decisions for D3-01, D3-02 (qualification process, Groq-direct route, and `openai/gpt-oss-20b` pin — all approved), D3-03, and D3-04. ✅ Done 2026-10-12.
2. Create `reports/docs/phases/phase_3/implementation_plan.md` only after this draft is reviewed and approved; maintain the repository's established phase-plan format.
3. Create the Phase 3 `execution_plan.md` from the approved decisions, with staged dependencies and evidence gates. No stage may depend on an unresolved material decision.
4. Confirm the repository's existing feature-SDD path convention before creating feature directories. Create only the SDDs needed for the approved substantial features.
5. Implement one approved execution stage at a time. Stop if actual repository evidence changes the decision basis or if a material architecture/scope/cost/security trade-off emerges.
6. Update accepted ADRs in `reports/docs/architecture/system_design.md` §6 only after the corresponding decision is approved and the implementation evidence supports it. Do not treat this phase plan as a second ADR source of truth.

---

## 8. Post-Implementation Review & Remediation (completed 2026-10-19, Stage 9)

| Review question | Evidence recorded | Status |
|---|---|---|
| Did primary success and automatic fallback meet the approved policy? | `tests/integration/test_gateway_resilience.py::test_primary_success_skips_fallback` (fallback transport receives zero calls), `::test_primary_timeout_falls_back_once`, `::test_primary_connection_failure_falls_back_once`, `::test_primary_eligible_server_error_falls_back_once`, `::test_primary_429_falls_back_once_without_same_provider_retry`, `::test_primary_provider_auth_rejection_falls_back_once`, `::test_malformed_primary_success_falls_back_once`; unit coverage in `tests/unit/test_gateway_service.py`. Qualification evidence (2026-10-12, operator-run, sanitized): Gemini `gemini-2.5-flash` HTTP 200 ×2 at 2176.2/1326.1 ms; Groq `openai/gpt-oss-20b` HTTP 200 ×2 at ~410 ms. | ✅ Satisfied |
| Were latency and max-attempt bounds respected under forced faults? | `::test_timeout_bounds_propagate_to_shared_transport` (15 s primary / 20 s fallback reach the shared transport), `::test_repeated_dual_failures_never_exceed_two_attempts_per_call` (exactly one primary + one fallback per call, no third attempt), `::test_primary_429_falls_back_once_without_same_provider_retry` (zero same-provider retries). `GatewayService.__init__` rejects any `max_attempts != 2` or `retries_per_provider != 0` (`tests/unit/test_gateway_service.py::test_service_rejects_non_policy_attempt_settings`). | ✅ Satisfied |
| Was breaker behavior consistent with the pinned `pybreaker` version? | `pybreaker==1.4.1` pinned (`pyproject.toml` `>=1.4.1,<2`; `uv.lock` 1.4.1) and its transition semantics verified against the installed source. 25 policy/transition tests in `tests/unit/test_provider_resilience.py` (closed→open at 3 eligible failures, open skip without provider call, half-open probe success closes, failed probe reopens, provider independence, deterministic clock, single-probe serialization) plus `::test_consecutive_eligible_failures_open_primary_breaker`, `::test_recovered_primary_is_used_after_open_interval`, `::test_failed_half_open_probe_reopens_breaker`, `::test_provider_breaker_state_is_independent`, `::test_half_open_probe_is_serialized_to_one_in_flight`. | ✅ Satisfied |
| Were provider events useful, complete, and redacted? | 10 captured-log tests in `tests/unit/test_gateway_events.py` (schema `v1`, fixed per-category messages, allowlist redaction, unknown usage/cost serialized null) plus `::test_event_sequence_and_metadata_on_fallback_success` (ordering, correlation ID, provider/model, attempt numbers, required field set), `::test_redaction_prevents_prompt_response_secret_borrower_leakage` (prompt/response/secret/borrower sentinels absent from all emitted records), `::test_unknown_usage_keeps_cost_unknown`. | ✅ Satisfied |
| Was usage/cost measured accurately where possible and marked unknown otherwise? | Provider-reported usage observed live on both legs (2026-10-12). Rates are versioned configuration with source and date in `params.yaml` (`rate_date: 2026-10-12`; sources: Google AI Studio Pricing, Groq published production rates). Cost is computed only from trustworthy usage **and** a known rate — `calculate_cost_usd` returns `None` (never `0.0`) otherwise (`::test_unknown_usage_keeps_cost_unknown`, `tests/unit/test_gateway_events.py::test_build_result_event_unknown_cost_without_rates`). Free-tier access is not represented as a permanent price. | ✅ Satisfied (cost is per-call; report-level cost not yet measurable — see §11.4 R5) |
| Did the phase preserve EvidenceBundle v1 and deterministic Tier 1–2 outputs? | `git diff 166ec738..HEAD -- src/schemas src/tier1_ml src/tier2_simulation src/pipelines` is **empty** (no source change to schemas or deterministic tiers). Full suite `uv run pytest` → 191 passed / 4 skipped; Ruff clean; Pyright 0 errors. Representative deterministic smoke produced a valid v1 bundle (PD 0.966667, rating `CCC/C`, P10/P50/P90 0.937583 / 0.976863 / 0.993034). Stage 8 boundary fixture confirmed LLM content/objects are rejected by the deterministic paths and removed afterwards. | ✅ Satisfied |
| What diverged from the approved plan, and why? | (1) **Fallback provider changed from HF to Groq-direct** — approved during D3-02 qualification with documented causes, recorded as ADR-034 (supersedes ADR-009's fallback designation only). (2) **`httpx` promoted from dev to runtime dependencies** and **`pybreaker` added** — the two approved runtime changes (D3-01, RES-T01); no other dependency added. (3) **HTTP 402 classified as `PROVIDER_UNAVAILABLE`, not an auth error** — corrective refinement from Stage 5 qualification, inside D3-05's "status plus machine-readable reason" rule. (4) **Feature `003_provider_observability` was not created as a separate SDD** — merged into `001`/`002` as §4 explicitly permitted. No divergence in EvidenceBundle v1, deterministic tiers, attempt/retry policy, or event schema. | ✅ Deviations accepted (owner: project operator; rationale recorded above) |
| What remediation remains, with priority and phase ownership? | No blocking item. Eight residual risks with explicit classification and ownership are recorded in §11.4 (R1 process-local breaker state, R2 opt-in live smoke, R3 free-tier provider limits, R4 cost-rate reference staleness, R5 no Tier 3 consumer yet, R6 pre-existing `dvc[s3]` extra, R7 fallback-model availability drift, R8 no cross-provider semantic-equivalence claim). None blocks closure. | ✅ Accepted risks — no blocking remediation |

All eight rows were completed with evidence; no `_pending_` marker remains. Any issue raised after closure must be classified as blocking, accepted risk with rationale/owner, or deferred to a named later phase.

---

## 9. Phase Closure

Phase 3 can be closed only after:

- [x] Human-approved material decisions are reflected in the execution plan and applicable SDDs. (D3-01…D3-06 in §5; SDDs `001`/`002` approved 2026-10-12; execution plan approved 2026-10-12.)
- [x] The exact fallback model is verified and pinned, or the phase is explicitly blocked pending an approved alternative. (`openai/gpt-oss-20b` on Groq-direct; qualification evidence 2026-10-12; ADR-034.)
- [x] Primary success, automatic fallback, breaker behavior, recovery, malformed output, and dual-provider failure are covered by deterministic tests. (110 mock-transport tests; see §8 and §11.1.)
- [x] Events demonstrate route selection, failure/fallback, latency, breaker behavior, and usage/cost-known status without leaking secrets or sensitive content. (Stage 4 + Stage 7/8 redaction and event-completeness tests.)
- [x] Existing 81-pass / 3-skip baseline is reconciled against post-change test results; Ruff and Pyright remain clean, with any change explained. (81/3 → 169/3 at Stage 6 → **191 passed / 4 skipped** at Stage 8; the 4th skip is the opt-in live smoke; Ruff clean; Pyright 0 errors.)
- [x] EvidenceBundle v1 and Tier 1–2 deterministic behavior remain unchanged. (Empty source diff vs baseline 166ec738; Stage 8 comparison and boundary falsification.)
- [x] ADR updates are consolidated in `reports/docs/architecture/system_design.md` §6; no competing ADR source is created. (ADR-034 present in §6; ADR-009 body preserved with a status-line supersession note; no other ADR source created.)
- [x] PIR rows are completed with evidence; no `_pending_` remains unless a formally accepted exception is recorded. (All eight rows completed in §8; no `_pending_` remains.)
- [x] The Phase 3 exit criteria are explicitly marked satisfied or not satisfied with reasons. (§11.1 traceability table.)

**Closure status:** ✅ **Phase 3 closed 2026-10-19** — all exit criteria satisfied and evidenced; human sign-off recorded (§11.5).  
**Human sign-off:** ✅ **Granted 2026-10-19 by the project operator** (Sebastián Garrido Arévalo), in response to the Stage 9 closure request.  
**Next phase:** Phase 4 may begin only after Phase 3 exit criteria are satisfied and the Phase 4 schema/persona design is separately planned and approved.

---

## 10. Human Decision Record

Please record approval explicitly; silence is not approval.

| Decision | Approved choice / changes requested | Approver decision | Date |
|---|---|---|---|
| D3-01 Transport and adapters | Approved Option B | Approved | 2026-10-11 |
| D3-02 Fallback-model qualification and final pin | Pinned: `openai/gpt-oss-20b` on Groq-direct (all acceptance items evidenced) | Approved (pin granted; new ADR at consolidation) | 2026-10-12 |
| D3-03 Resilience policy and proposed initial values | Approved Option B with proposed values as starting points | Approved | 2026-10-11 |
| D3-04 Structured event and cost logging | Approved Option B | Approved | 2026-10-11 |
| D3-05 Gateway contract | Reviewed via approved `001_llm_gateway` SDD (contract + UA + taxonomy) | Approved with SDD | 2026-10-12 |
| D3-06 Reliability test matrix | Covered by approved execution plan Stages 4–7 + acceptance checklist | Approved with execution plan | 2026-10-12 |

**Overall phase-plan approval:** ✅ Granted 2026-10-12 (all decisions, SDDs, and execution plan approved).  
**Implementation authorization:** ✅ Granted 2026-10-12 (operator authorized: "begin Stage 0").

---

## 11. Stage 9 — Phase Closure Evidence (2026-10-19)

### 11.1 Exit criteria (§1.5) — documentation-to-reality audit

| # | Exit criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | A healthy primary provider succeeds through the provider-neutral gateway contract | ✅ Satisfied | `tests/integration/test_gateway_resilience.py::test_primary_success_skips_fallback` — typed `GatewayResult` (provider `gemini`, model `gemini-2.5-flash`), fallback transport receives **zero** calls |
| 2 | A forced primary failure or timeout automatically invokes the fallback without an unhandled exception | ✅ Satisfied | Timeout, connection failure, eligible 5xx, 429, provider 401, and malformed-200 tests each route to Groq; no raw provider/transport exception crosses the boundary |
| 3 | Both-provider failure returns a controlled, typed outcome | ✅ Satisfied | `::test_fallback_failure_yields_typed_dual_failure` (`DUAL_PROVIDER_FAILURE`, sanitized cause, terminal event), `::test_both_breakers_open_yields_dual_failure_without_provider_calls` |
| 4 | Circuit-breaker transitions and fallback behavior are bounded, deterministic, and covered by tests | ✅ Satisfied | 25 policy/transition unit tests + 5 Stage 7 breaker tests; deterministic clock; `pybreaker==1.4.1` semantics verified against installed source |
| 5 | Events record provider/model, outcome, latency, fallback/breaker transitions, and usage/cost when trustworthy, excluding sensitive content and credentials | ✅ Satisfied | `::test_event_sequence_and_metadata_on_fallback_success`, `::test_redaction_prevents_prompt_response_secret_borrower_leakage`, `::test_unknown_usage_keeps_cost_unknown`, 10 Stage 4 captured-log tests |
| 6 | The fallback model is pinned and its endpoint, access, response shape, and availability are verified at implementation time | ✅ Satisfied | `openai/gpt-oss-20b` @ `https://api.groq.com/openai/v1` via `GROQ_API_KEY`; qualification 2026-10-12 (HTTP 200 ×2 at ~410 ms, usage metadata present, clean 400 on malformed); re-verified in the Stage 0 baseline and locked by `tests/unit/test_groq_adapter.py` |
| 7 | Deterministic Tier 1–2 behavior and EvidenceBundle v1 remain unchanged; baseline suite and static checks pass | ✅ Satisfied | Empty diff for `src/schemas src/tier1_ml src/tier2_simulation src/pipelines` vs baseline 166ec738; 191 passed / 4 skipped; Ruff clean; Pyright 0 errors; Stage 8 boundary falsification |
| 8 | PIR completed, accepted ADRs consolidated in `system_design.md` §6, and all exit criteria carry evidence | ✅ Satisfied | §8 PIR complete; ADR-034 present in §6; this table |

### 11.2 Requirement coverage — SDD requirement → implementation → verification

| Requirement | Implementation | Verification |
|---|---|---|
| GW-FR-01 typed request, correlation ID, provider-neutral messages | `src/gateway/contracts.py::GatewayRequest` | `tests/unit/test_gateway_contracts.py` |
| GW-FR-02 provider/model from validated config; caller cannot set base URL | `src/gateway/config.py::GatewayConfig/ProviderSettings`; request contract exposes no URL field | `tests/unit/test_gateway_contracts.py` (bounds, unknown fields, missing config) |
| GW-FR-03 secrets from environment; never committed or logged | `src/gateway/config.py::resolve_api_key`; `.env` untracked + gitignored | Stage 8 credential scan (clean) |
| GW-FR-04 normalized typed result; raw HTTP never escapes | `src/gateway/providers/base.py::parse_chat_response` | `tests/unit/test_gemini_adapter.py`, `test_groq_adapter.py`, `test_gateway_service.py` |
| GW-FR-05 missing/malformed required fields are failures | fail-closed `parse_chat_response` | `::test_malformed_primary_success_falls_back_once`; adapter tests |
| GW-FR-06 bounded typed error taxonomy | `src/gateway/contracts.py::GatewayErrorCategory` (10 members) | `tests/unit/test_provider_resilience.py`; adapter taxonomy tests |
| GW-FR-07 structured events for every attempt and outcome | `src/gateway/events.py` | `tests/unit/test_gateway_events.py`; `::test_event_sequence_and_metadata_on_fallback_success` |
| GW-FR-08 event field completeness | `src/gateway/contracts.py::ProviderEvent`; schema `v1` | `::test_serialize_event_schema_version_and_keys`; integration event test |
| GW-FR-09 unknown usage/cost stays unknown; versioned rates with source/date | `src/gateway/config.py::calculate_cost_usd`; `params.yaml` `cost_rates` (`rate_date`, `rate_source`) | `::test_build_result_event_unknown_cost_without_rates`; `::test_unknown_usage_keeps_cost_unknown` |
| GW-FR-10 no prompts/completions/secrets/headers logged | `src/gateway/events.py::redact_value` allowlist + fixed per-category messages | `::test_falsification_sentinel_values_redacted`; `::test_redaction_prevents_prompt_response_secret_borrower_leakage` |
| GW-FR-11 browser-style `User-Agent` on Groq requests | `src/gateway/providers/base.py::build_headers`; `GatewayConfig.default_user_agent` | `tests/unit/test_groq_adapter.py` (UA assertion) |
| GW-FR-12 injectable/mockable transport; no live credentials in CI | all tests use `httpx.MockTransport`; live smoke opt-in | full suite; `::test_live_gateway_smoke_opt_in` skipped by default |
| GW-FR-13 preserve EvidenceBundle v1 and deterministic tiers | no change to `src/schemas`, `src/tier1_ml`, `src/tier2_simulation`, `src/pipelines` | Stage 8 diff + boundary falsification |
| RES-FR-01 one primary + one fallback attempt maximum | `src/gateway/service.py::GatewayService.complete` | `::test_repeated_dual_failures_never_exceed_two_attempts_per_call` |
| RES-FR-02 15 s primary / 20 s fallback timeouts | `ProviderSettings.timeout_s`; per-attempt timeout passed to the adapter | `::test_timeout_bounds_propagate_to_shared_transport` |
| RES-FR-03 zero same-provider retries | `retries_per_provider=0`; constructor guard rejects any other value | `::test_service_rejects_non_policy_attempt_settings`; 429 test |
| RES-FR-04 independent breaker per provider | `src/gateway/resilience.py::GatewayBreakers` (rejects identical provider legs) | `::test_provider_breaker_state_is_independent` |
| RES-FR-05 opens after 3 consecutive eligible failures | `breaker_failure_threshold=3` + `exclude` eligibility policy | `::test_consecutive_eligible_failures_open_primary_breaker`; unit threshold test |
| RES-FR-06 30 s interval, one half-open probe | `pybreaker` `reset_timeout` / `success_threshold=1` | recovery, reopen, and probe-serialization tests |
| RES-FR-07 eligible failures and breaker-open trigger fallback | `src/gateway/resilience.py::is_fallback_eligible` | eligibility matrix tests; Stage 7 routing matrix |
| RES-FR-08 invalid input/config/missing credentials are not retried | `is_fallback_eligible` / `is_breaker_failure` | `::test_primary_local_credential_fault_fails_fast`; `::test_deterministic_primary_4xx_rejection_fails_fast` |
| RES-FR-09 classify on status + machine-readable reason | `src/gateway/providers/base.py::classify_http_error(status, reason)` (402 and 403-balance handled) | `test_billing_402_is_provider_unavailable_and_eligible` |
| RES-FR-10 malformed/empty responses are never success | fail-closed parsing in the adapters | malformed-200 integration test; adapter malformed tests |
| RES-FR-11 dual failure = one sanitized gateway-level failure | `GatewayError(DUAL_PROVIDER_FAILURE)` with sanitized cause and correlation ID | `::test_fallback_failure_yields_typed_dual_failure` |
| RES-FR-12 routing and breaker transitions emit events | `build_attempt_event` / `build_error_event` / `build_breaker_event` | `test_breaker_transitions_emit_single_redacted_event`; Stage 7 transition tests |
| RES-FR-13 deterministic mocked tests, no live credentials | 110 mock-transport tests | full suite; live smoke opt-in and skipped |
| RES-FR-14 no EvidenceBundle v1 / deterministic Tier 1–2 change | no change to those modules | Stage 8 diff + boundary falsification |

### 11.3 ADR, cross-reference, and invariant audit

**ADRs**

- **ADR-034** is present in `reports/docs/architecture/system_design.md` §6 with its acceptance record (verified 2026-10-19; no edit required).
- **ADR-009** was **not** rewritten: its decision body is preserved verbatim, and only its status line records the supersession ("fallback designation superseded by ADR-034; gateway architecture, `pybreaker` direction, and Gemini-primary decisions stand unmodified").
- **No new ADR was created** in Phase 3: implementation required no new architectural decision, and this plan was not used as a second ADR source of truth (§7 step 6).
- **Stale HF-fallback references** were corrected in active normative records only: removed from the `system_design.md` §7 open-notes list (resolved item, per §8 protocol item 3), the `.env.example` secret placeholder, the Phase 3 package README status, and the SDD/plan/tasks authorization lines. Historical records are preserved in ADR-009's body, ADR-034's context, and the D3-02 qualification narrative.
- **Status records updated** to reflect actual implementation: `system_design.md` §2 phase table and §4 component statuses, §3/§5 annotations, `reports/docs/implementation_roadmap.md` Phase 3 entry, the project `README.md` milestone table, and the Phase 3 package README.

**Invariants**

| Invariant | Compliance in Phase 3 | Evidence |
|---|---|---|
| INV-1 — the deterministic core must never accept LLM-generated output | The gateway is a Tier 3 infrastructure boundary; it never reads or writes Tier 1–2 state | No gateway module imports `src/tier1_ml` / `src/tier2_simulation`; only `src/config/loader.py` references the gateway, and only as an optional config field; Stage 8 boundary falsification confirmed LLM text/objects are rejected by the deterministic paths |
| INV-2 — all cross-tier/inter-agent exchange flows through the versioned EvidenceBundle | The gateway exposes its own typed contract and does not write EvidenceBundle state; Phase 3 added no v2 field | `src/gateway/contracts.py` is a separate contract; `src/schemas/evidence_bundle.py` unchanged |
| INV-6 — every LLM call routes through the gateway's circuit breaker | The only production caller of the provider adapters is `GatewayService`, which invokes them through `GatewayBreakers.call`; no direct provider SDK or raw HTTP client call exists elsewhere | `src/gateway/service.py` is the sole production importer of `invoke_gemini` / `invoke_groq`; no `httpx.Client` is constructed outside `src/gateway/` and tests; no provider SDK dependency added (D3-01) |
| INV-3 / INV-4 / INV-5 / INV-7 / INV-8 / INV-9 / INV-10 | Not engaged by Phase 3 — no model promotion, no persona, no divergence scoring, no data-contract change, no auto-approval path | No change to `src/tier1_ml`, `src/tier2_simulation`, `src/schemas`, `src/pipelines`, or `gx/` |

### 11.4 Residual risks and ownership

| ID | Risk | Classification | Owner | Mitigation / trigger for revisit |
|---|---|---|---|---|
| R1 | Breaker state is process-local (`pybreaker` in-memory storage); no cross-process coordination | Accepted risk (D3-02 clarification 5) | Project operator | Revisit on deployment evidence (multi-worker deployment) |
| R2 | The live-provider smoke test is opt-in, so provider API drift or credential expiry surfaces only on a human-triggered run | Accepted risk | Project operator | Run `ACRAS_LIVE_GATEWAY_SMOKE=1` before any gateway-dependent release; re-qualify pins if a live call fails |
| R3 | Both providers are free-tier; rate limits and availability are outside project control | Accepted risk | Project operator | A funded tier would require a new explicit decision before production use |
| R4 | Cost rates are versioned reference values dated 2026-10-12 and may drift from provider billing | Accepted risk (non-blocking) | Project operator | Refresh `rate_date`/`rate_source` on pricing change; unknown cost stays unknown by design |
| R5 | No Tier 3 consumer exists yet, so report-level p50 (<2 min) and per-report cost (<$0.15) are not measurable; Phase 3 evidences per-call latency/cost only | Deferred to Phase 4/5 (by design) | Phase 4/5 planning | Validate at the first report-producing consumer |
| R6 | `dvc[s3]` extra retained despite the local-remote decision (gap G5) | Pre-existing, explicitly out of scope, non-blocking | Project operator | Separate issue; no Phase 3 change |
| R7 | The pinned fallback model is a free-tier property and could be withdrawn by the provider | Accepted risk | Project operator | ADR-034 requires a new decision if the pin stops qualifying; the gateway handles a withdrawn model as an ordinary provider failure |
| R8 | No semantic-equivalence claim between Gemini and Groq is made | By design (plan §2 risk note) | Phase 5 evaluation | Assess cross-provider persona quality and grounding in Phase 5 |

No residual risk is blocking. None is relabelled from blocking without approval.

### 11.5 Human sign-off record

| Item | Record |
|---|---|
| Gate 9 conditions | All satisfied: stages 0–8 passed; every exit criterion backed by evidence (§11.1); PIR complete (§8); accepted ADRs and active cross-references consistent (§11.3); architecture/status records reflect actual implementation; no material unresolved finding remains (§11.4) |
| Human sign-off | ✅ **Granted 2026-10-19 by the project operator (Sebastián Garrido Arévalo)**, explicitly, in response to the Stage 9 closure request. All Gate 9 conditions were satisfied at the time of approval. Silence was not treated as approval — the approval was recorded explicitly. |
| Phase 4 | Not authorized by this closure. Phase 4 requires its own planning, schema/persona design, and approval |
