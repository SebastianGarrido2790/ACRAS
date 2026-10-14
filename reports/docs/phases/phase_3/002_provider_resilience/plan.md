# Feature Plan — 002 Provider Resilience
**Status:** ✅ Approved 2026-10-12 (policy answers recorded; breaker-semantics checkpoint at RES-T01/RES-T05). No implementation authorization.

## Design
Resilience orchestration stays in the gateway layer, separate from provider adapters. One primary attempt, then at most one fallback attempt. Adapters perform zero retries; no implicit routing or unbounded loops.

## Breakers and routing
- Use `pybreaker` after verifying and pinning a compatible version and testing real transition semantics.
- Independent Gemini and Groq breakers; initial state process-local unless a separately approved requirement says otherwise.
- Validate request/configuration before any provider call.
- If primary breaker is open, skip primary and route to fallback.
- Otherwise call primary with 15 s timeout. Valid response returns success.
- On approved eligible failure, record event and call fallback with 20 s timeout, unless its breaker is open.
- Valid fallback response returns success marked as fallback. If fallback fails, return controlled typed gateway failure.
- Enforce two total attempts, no same-provider retries, no raw provider exceptions at public boundary.
- Final behavior for 429, primary auth/configuration faults, and malformed responses follows the approved clarification decisions.

## Failure classes
Eligible availability faults: timeout, connection failure, provider 5xx, approved rate-limit case, breaker open, known provider unavailable/balance errors. Local invalid input/configuration and missing credentials are non-retryable. Auth/configuration errors are classified explicitly. Invalid provider output never counts as success.

## Tests
Mocked primary success/no fallback; primary 5xx/connection/timeout to fallback; open breaker; fallback failure/dual failure; threshold/open/half-open/recovery; invalid config/input/credentials; 429/auth/malformed-response policy; exact timeouts and two-attempt maximum; event/redaction assertions. Live qualification is manual and separate from CI.

## Risks
Library semantics differ → pin/test. Retry amplification → zero retries in adapters. Misclassified auth/billing → status plus safe reason. Probe stampede → prove scope. Malformed output → fail closed. Latency/cost conflict → return for approval, do not silently revise.

## Approval gate
Resolve clarification questions, approve gateway contract, verify deployment scope and `pybreaker` semantics, then approve plan/tasks.
