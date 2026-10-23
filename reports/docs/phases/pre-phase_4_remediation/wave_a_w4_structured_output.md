# Wave A · W-A4 Evidence Report — Gateway Structured-Output Qualification

*ACRAS · 2026-10-23 · Wave A (measure + bounded-repair contract; no orchestration built).*
*Source: [`execution_plan.md`](execution_plan.md) §2 W-A4 · authority: `remediation_plan.md` §4 R-05 / D-05 / D-06.*

## 1. Result summary

| Item | Gemini `gemini-2.5-flash` | Groq `openai/gpt-oss-20b` |
| --- | --- | --- |
| Calls requested / completed | 15 / 15 | 15 / 15 |
| Schema-valid (`PersonaVerdict`) | 15 / 15 (100%) | 15 / 15 (100%) |
| Wilson 95% CI | [0.796, 1.0] | [0.796, 1.0] |
| One-sided 95% lower bound | 0.847 | 0.847 |
| p50 / p95 latency | 796.6 / 3226.5 ms | 680.9 / 1572.1 ms |
| `reject` enum exercised | 5/15 | 5/15 |
| `lean` at ±1.0 bound | −1.0 and +1.0 observed | −1.0 and +1.0 observed |
| Reasoning/thinking tokens | 72–354 (residual) | 76–381 (`details`) |

Both providers returned schema-valid `PersonaVerdict` JSON on **every completed call** when JSON mode was requested through the gateway, exercising all three recommendation enums and both `lean` bounds. The structured-output path **passes qualification**; D-05's preferred route (gateway-direct + Pydantic validation) is confirmed viable for both providers.

## 2. Method

- N = 15 calls per provider, submitted with up to 3 concurrent workers, paced (≥6 s between call starts) to stay within free-tier rate limits; a **fresh** `GatewayService`/breaker per call isolates transient failures.
- `GatewayRequest(json_mode=True)` → the adapter now forwards `response_format: {"type": "json_object"}` (see §6 code changes).
- Each response parsed/validated with `parse_persona_verdict` (Pydantic `PersonaVerdict` schema), which rejects wrong enums, out-of-range `lean`/`confidence`, and short `rationale`.
- Prompts directed one of three outcomes (`reject`/`approve`/`conditional`) so the enum set and `lean` bounds were actually exercised, not assumed.
- Raw `usage` captured inside the gateway call path (injected recording client, INV-6 preserved) to attribute reasoning/thinking tokens.

## 3. Token accounting (falsification)

- **Gemini** reports only `prompt/completion/total`; thinking tokens are the `total − prompt − completion` residual (observed 72–354 per call). They are counted once in `total`, excluded from `completion`.
- **Groq** reports `completion_tokens_details.reasoning_tokens` (observed 76–381 per call), already included in `completion`; `total = prompt + completion`.
- Both therefore **attribute reasoning/thinking tokens**, satisfying the W-A4 falsification. The residual-vs-`details` split is the same discrepancy recorded in W-A1; resolving it (a `details` passthrough) remains a Wave B change, not needed for this qualification.

## 4. Mock-transport validation (falsification)

Unit tests (`tests/unit/test_persona_verdict.py`) prove, with no live dependency:

- malformed JSON → `PersonaVerdictValidationError` (fails loudly);
- truncated JSON → `PersonaVerdictValidationError`;
- wrong enum (`decline`) → `PersonaVerdictValidationError`;
- `lean` out of range (1.5) → rejected; short `rationale` → rejected;
- `with_bounded_repair` recovers on the second attempt and gives up after **exactly one** repair re-ask (D-06/R-05 "at most one bounded repair").

## 5. Operational finding (rate limits + breaker cascade)

An earlier unpaced burst (15 calls/provider, 3-way concurrency, no throttle) exposed a **free-tier rate-limit + 3-failure breaker cascade**: after three rate-limit errors the process-local breaker opened, and subsequent attempts failed as `circuit_breaker_open`, producing `dual_provider_failure` even though the model itself was available. This is an **operational** finding, not a schema-validity finding — every call that actually completed was schema-valid. It is relevant to R-05/D-06: Tier 3 must budget for breaker/rate-limit behaviour on free-tier keys and must not conflate a rate-limit/breaker failure with a schema failure.

## 6. Code changes made (W-A4 deliverable)

- `src/gateway/providers/base.py`: `build_chat_payload` now forwards `response_format: {"type": "json_object"}` when `request.json_mode` is set.
- `src/schemas/persona_verdict.py` (new): `PersonaVerdictValidationError`, `parse_persona_verdict`, `with_bounded_repair`.
- `src/schemas/__init__.py`: exports the new names.
- Tests: `tests/unit/test_persona_verdict.py` (new); `tests/unit/test_gemini_adapter.py` (json_mode payload tests).

## 7. D-05 recommendation

Adopt **gateway-direct calls + Pydantic validation** (Option A in R-05). Both configured providers return schema-valid structured output through the gateway; no Pydantic AI adapter boundary is needed. The `details` passthrough (W-A1) and a Tier 3 orchestration repair policy (R-05 action 3) are deferred to Wave B/Phase 4 but are unblocked by this evidence.

## 8. Open items

1. `usage.details` still dropped by `parse_chat_response`; reasoning is inferred via residual (Gemini) or already inside `completion` (Groq). Recommend the Wave B change-managed `details` passthrough.
2. Free-tier rate limits made a tight unpaced N=15 burst unreliable; production/qualification on higher quotas should re-confirm under sustained concurrency.
