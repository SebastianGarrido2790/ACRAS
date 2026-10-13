# Feature Specification — 002 Provider Resilience
**Status:** Draft for human review; clarification gate open. **Implementation authorization:** Not granted.

## Purpose
Bounded failover from Gemini primary to Groq-direct fallback, with independent circuit breakers and controlled typed failure when both providers fail.

## Functional requirements
- **RES-FR-01:** At most one primary and one fallback attempt per gateway call.
- **RES-FR-02:** Primary timeout 15 s; fallback timeout 20 s, unless evidence shows conflict and a revised decision is approved.
- **RES-FR-03:** Zero same-provider retries in the initial implementation.
- **RES-FR-04:** Independent breaker per provider.
- **RES-FR-05:** Breaker opens after 3 consecutive eligible failures/provider.
- **RES-FR-06:** Initial open/reset interval 30 s; at most one half-open probe/provider, subject to pinned `pybreaker` semantics.
- **RES-FR-07:** Eligible timeout, connection/provider/server failure, breaker-open, and approved rate-limit/balance cases trigger fallback.
- **RES-FR-08:** Invalid input/configuration and missing credentials are not retried as transient provider failures.
- **RES-FR-09:** Classify using status plus safe machine-readable reason, not status alone.
- **RES-FR-10:** Malformed/empty/schema-invalid responses are never success; fallback behavior must be explicit and tested.
- **RES-FR-11:** Dual failure returns one sanitized gateway-level failure with correlation/event identifiers.
- **RES-FR-12:** Routing and breaker transitions emit structured events.
- **RES-FR-13:** Deterministic mocked tests prove routing, attempt limits, transitions and recovery without live credentials.
- **RES-FR-14:** Do not alter EvidenceBundle v1 or deterministic Tier 1–2 behavior.

## Approved starting values
Primary 15 s; fallback 20 s; retries 0; breaker threshold 3; open/reset 30 s; one half-open probe/provider; maximum two total attempts. These are approved starting values, not proof of report-level latency/cost compliance. Verify actual `pybreaker` behavior and do not silently change values.

## Acceptance criteria
Primary success skips fallback; eligible failure/timeout invokes fallback once; open breaker routes to fallback; dual failure is controlled; breaker transitions/recovery match pinned-library semantics; invalid local errors do not trigger inappropriate retries; malformed output cannot succeed; max attempts/timeouts hold; events are auditable/redacted; baseline checks pass.

## Clarification gate — answer before approval
1. Should HTTP 429 trigger immediate fallback? Recommendation: yes, no same-provider retry.
2. If primary auth fails, should fallback still be attempted once while raising a high-severity event? Recommendation: yes, with explicit configuration-fault classification.
3. Should malformed successful HTTP responses trigger fallback once? Recommendation: yes.
4. Is half-open probe scope one probe per provider per process, or must it coordinate across instances?
5. Confirm breaker state is process-local for Phase 3. Recommendation: yes, unless deployment evidence requires shared state.

**Definition of done:** approved policy is implemented and deterministic routing/fault/recovery tests pass. This draft does not authorize implementation.
