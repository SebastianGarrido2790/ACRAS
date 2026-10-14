# Feature Specification — 001 LLM Gateway
**Status:** ✅ Approved 2026-10-12; clarification gate closed. **Implementation authorization:** Not granted (separate gate).

## Purpose and boundaries
Provide a provider-neutral typed LLM gateway for future Tier 3 callers. Phase 3 includes Pydantic contracts, thin `httpx` adapters for Gemini primary and Groq-direct fallback, response validation, configuration, and redacted events. It does not implement personas, alter EvidenceBundle v1, or call/mutate deterministic Tier 1–2 calculations.

## Functional requirements
- **GW-FR-01:** Accept a typed request with correlation ID and provider-neutral messages/settings.
- **GW-FR-02:** Resolve provider/model from validated configuration; callers cannot provide arbitrary base URLs.
- **GW-FR-03:** Read secrets from approved environment/secret configuration; never commit or log credentials.
- **GW-FR-04:** Normalize provider success into a typed result; raw HTTP objects never escape.
- **GW-FR-05:** Missing/malformed required response fields are failures, never success.
- **GW-FR-06:** Normalize provider errors into a bounded typed taxonomy.
- **GW-FR-07:** Emit structured events for every provider attempt and final outcome.
- **GW-FR-08:** Events include timestamp, correlation/event ID, provider/model, attempt, outcome/category, latency, fallback/breaker details, usage and cost when known.
- **GW-FR-09:** Unknown usage/cost stays unknown. Compute cost only from explicit versioned rates with source/date.
- **GW-FR-10:** Do not log prompts, completions, secrets, authorization headers, or sensitive payloads.
- **GW-FR-11:** Groq requests send a browser-style `User-Agent`, covered by a test.
- **GW-FR-12:** Use injectable/mockable HTTP transport; routine CI needs no live credentials/network.
- **GW-FR-13:** Preserve EvidenceBundle v1 and deterministic Tier 1–2 behavior.

## Non-functional requirements
Auditability, redaction, bounded control flow, no implicit provider selection/hidden retries, minimal dependencies, and compatibility with existing serving architecture.

## Provider pin
Fallback: Groq-direct `https://api.groq.com/openai/v1`, model `openai/gpt-oss-20b`, secret via `GROQ_API_KEY`. Operator-reported qualification on 2026-10-12: two HTTP 200 completions around 410 ms, usage metadata present, malformed request returned HTTP 400. Revalidate at implementation time; free-tier conditions are not a permanent production-price guarantee. Gemini primary model/endpoint and its environment-variable convention must be verified from repository authority; do not infer them here.

## Proposed contract for review
Provisional types: `GatewayRequest`, `GatewayResult`, `ProviderUsage`, `GatewayError`, `ProviderEvent`. Include bounded typed fields, safe normalized errors, optional usage, latency and correlation IDs. Exact field layout is not approved. Do not convert gateway output to `PersonaVerdict` or EvidenceBundle fields in Phase 3.

## Acceptance criteria
Typed contracts and config validate; provider-specific objects do not escape; malformed responses fail closed; events are complete and redacted; unknown cost stays unknown; User-Agent is tested; full pytest/Ruff/Pyright pass; EvidenceBundle v1 and deterministic tiers remain unchanged.

## Clarification gate — resolved and approved 2026-10-12
1. Gemini primary: `gemini-2.5-flash` via Google's OpenAI-compatible endpoint (substituted 2026-10-12 after `gemini-2.0-flash` proven retired; floating aliases rejected); model ID recorded in versioned non-secret config and verified live at implementation (same qualification discipline as the Groq leg). Env var: `GEMINI_API_KEY`.
2. Request messages: OpenAI-style role/content messages array (both providers speak it; no provider-specific templating in the gateway).
3. Structured JSON: envelope validation only in Phase 3; adapter `json_mode` support recorded as a capability flag for Phase 4 verdict parsing.
4. Secrets: `.env.example` placeholder + session/out-of-band supply (established HF/GROQ practice); variables `GEMINI_API_KEY`, `GROQ_API_KEY`. Never committed, logged, or echoed.
5. Failure representation: return `GatewayResult` on success; raise a single `GatewayError` (category field) on failure.

**Definition of done:** approved contract implemented and tested, redaction/regression checks pass, and evidence is recorded. This draft does not authorize implementation.
