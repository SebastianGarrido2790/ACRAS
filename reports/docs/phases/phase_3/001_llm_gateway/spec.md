# Feature Specification — 001 LLM Gateway
**Status:** Draft for human review; clarification gate open. **Implementation authorization:** Not granted.

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

## Clarification gate — answer before approval
1. What exact Gemini model ID/endpoint is authoritative, and where configured?
2. Should request messages be role/content messages or a single user input plus system instructions?
3. Is structured JSON output in Phase 3 scope, or deferred to Phase 4?
4. Which existing secret/environment convention and variable names should be used?
5. Should failure use a typed result/error union or one gateway-level exception?

**Definition of done:** approved contract implemented and tested, redaction/regression checks pass, and evidence is recorded. This draft does not authorize implementation.
