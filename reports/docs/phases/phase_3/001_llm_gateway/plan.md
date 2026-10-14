# Feature Plan — 001 LLM Gateway
**Status:** ✅ Approved 2026-10-12 (clarifications resolved; contract review checkpoint at GW-T03). No implementation authorization.

## Design
One provider-neutral gateway facade over shared `httpx` transport; thin Gemini and Groq adapters own URL/payload/header/response mapping. Gateway owns typed validation and attempt events; resilience feature owns fallback and breaker policy.

## Proposed boundaries (verify repository layout first)
- `src/gateway/contracts.py`: request/result/usage/error/event schemas.
- `src/gateway/client.py`: public gateway facade.
- `src/gateway/providers/gemini.py`, `groq.py`: provider adapters.
- `src/gateway/config.py`: validated non-secret settings and environment secret resolution.
- `src/gateway/events.py`: event construction, redaction and versioned cost computation.
- Unit/integration tests under the repository's established test layout.

## Implementation constraints
- Promote `httpx` to runtime dependency only in the approved implementation; pin via existing `uv` workflow.
- Inject transport for deterministic tests; explicit timeouts; no hidden retries.
- Groq base URL/model/auth are `https://api.groq.com/openai/v1`, `openai/gpt-oss-20b`, `GROQ_API_KEY`.
- Gemini base URL/model/auth are Google's OpenAI-compatible endpoint, `gemini-2.0-flash`, `GEMINI_API_KEY` (verify live at implementation).
- Send/test browser-style User-Agent on all adapters (generalized per approved clarification; Cloudflare-fingerprint evidence).
- Do not add `huggingface_hub`, provider SDKs, LangChain, LiteLLM, OTel, or Prometheus.
- Validate response structure before success. Unknown usage/cost is `None`; pricing requires versioned source/date.
- Redact prompts/completions, auth headers, keys and sensitive payloads.
- Error taxonomy proposal: timeout, connection error, rate limited, provider unavailable, invalid provider response, configuration/authentication error, breaker open, unknown provider error. Final categories require review.
- Do not change persona schemas or EvidenceBundle v1.

## Validation
Contract/config tests; mocked success, malformed/non-JSON/empty responses, non-2xx, timeout and connection failures; safe event/secret-redaction assertions; User-Agent assertion; full regression, Ruff, Pyright.

## Risks
Provider schema drift → fail closed and adapter tests. Secret leakage → centralized redaction tests. Free-tier changes → revalidate. Premature Phase 4 coupling → no persona/EvidenceBundle changes.

## Approval gate
Resolve spec questions, confirm Gemini configuration and repository paths, approve concrete contract/error semantics, then approve this plan/tasks before implementation.
