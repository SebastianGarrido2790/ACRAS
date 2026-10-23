# Wave A · W-A1 Evidence Report — Provider Pricing, Token Billing & Lifecycle

*ACRAS · 2026-10-23 · Wave A (measure-only, no config applied).*
*Source: [`execution_plan.md`](execution_plan.md) §2 W-A1 (30 min cap).*

## 1. Result summary

| Item | Result |
| --- | --- |
| Groq `openai/gpt-oss-20b` rate | **Verified correct** — $0.075 input / $0.30 output per 1M tokens |
| Gemini `gemini-2.5-flash` rate | **Wrong** — configured $0.075/$0.30 is a copy of Groq's block; primary source is $0.30 input / $2.50 output |
| Rate-duplicate root cause | Confirmed copy-paste: Gemini block cloned from Groq block |
| Gemini reasoning-token billing | Output price row is "response and reasoning" — thinking tokens bill as output tokens |
| Groq model lifecycle | Production model, no deprecation date |
| Gemini model lifecycle | **Unverified** — deprecation page returned transport errors; model still listed on current Vertex pricing page and served a live call on 2026-10-23 |
| Live-call token accounting | **Completed** — one live call per provider through `GatewayService` |
| Gemini token accounting | **Mismatch** — `completion_tokens` excludes reasoning (450 tokens); `total_tokens` includes it; current cost formula bills `completion_tokens` only, so it **undercounts** |
| Groq token accounting | **Consistent** — `completion_tokens` includes reasoning (81); `total_tokens = prompt + completion` |
| Reasoning counted once? | **Yes, on both** — Gemini reasoning appears once in the `total_tokens` residual; Groq reasoning appears once inside `completion_tokens`. Neither is double-counted as input and output. |
| Stop rule | Not triggered (rates resolved; no Gemini deprecation observed in the live call) |

## 2. Primary-source pricing evidence

| Provider / model | params.yaml (current) | Primary-source price (/1M tokens) | Source |
| --- | --- | --- | --- |
| `gemini-2.5-flash` | $0.075 in / $0.30 out | $0.30 in / $2.50 out (≤200K ctx); cached input $0.03 | Google Cloud Vertex AI Generative AI pricing |
| `openai/gpt-oss-20b` | $0.075 in / $0.30 out | $0.075 in / $0.30 out | console.groq.com/docs/models |

- Gemini 2.5 Flash input applies to "text, image, video"; audio input is $1.00/1M. Output $2.50/1M is stated as "Text output (response and reasoning)", i.e. thinking/reasoning tokens are billed as output at the $2.50 rate.
- Groq lists `openai/gpt-oss-20b` as a Production model at $0.075/$0.30 with 131,072-token context and 65,536 max completion tokens.

## 3. Live call evidence (2026-10-23)

One call per provider through `GatewayService.complete()`; prompt asked for `17*23` then `ACK`, `max_tokens=512`, `temperature=0`. Both returned the correct `391 ACK` with `finish_reason=stop`. Raw `usage` was captured via an injected recording client inside the gateway call path (INV-6 preserved); no prompt/completion content or credentials were logged.

| Provider / model | prompt | completion | total | reasoning | total−prompt−completion | latency | recorded cost | correct cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `gemini-2.5-flash` | 36 | 4 | 490 | 450 (inferred) | 450 | 3462 ms | $0.0000039 | $0.0011458 |
| `openai/gpt-oss-20b` | 101 | 92 (incl. 81) | 193 | 81 (reported) | 0 | 858 ms | $0.00003517 | $0.00003517 |

- **Gemini:** the compat response carried only `prompt_tokens` / `completion_tokens` / `total_tokens` — no `completion_tokens_details`. `total_tokens` (490) exceeds `prompt + completion` (40) by 450, which is the thinking-token residual. Reasoning is counted **once** (in the total), but **not** in `completion_tokens`.
- **Groq:** reported `completion_tokens_details.reasoning_tokens = 81`; `completion_tokens` (92) already includes them, and `total_tokens` (193) equals `prompt + completion`. Reasoning is counted **once**, inside completion.
- **Consequence for cost:** billable output is `total_tokens − prompt_tokens` on both providers (Groq: 92 = completion; Gemini: 454 = completion + reasoning). The current formula (`prompt × input + completion × output`) undercounts Gemini by 450 output tokens — about 55× low for this call once the corrected rate is applied. The rate error and the formula error compound: recorded $3.9e-6 vs correct $1.1458e-3 (~294× low).
- **Probe caveat:** `invoke_groq` hardcodes `fallback_used=True` (Groq is designed as the fallback adapter). Because this probe targeted Groq as primary, its `fallback_used` field is not a routing signal; the call was served on the first attempt.

## 4. Proposed `params.yaml` correction (deferred to Wave B — NOT applied)

```yaml
gemini-2.5-flash:
  input_per_m: 0.30     # was 0.075
  output_per_m: 2.50    # was 0.30
  rate_date: "2026-10-23"
  rate_source: "Google Cloud Vertex AI Generative AI pricing (Gemini 2.5 Flash, <=200K ctx)"
```

Companion cost-accounting change (also Wave B, not applied): compute output-billable tokens as `total_tokens − prompt_tokens` (equivalent to `completion_tokens` on Groq, and `completion + reasoning` on Gemini), or add an explicit `reasoning_tokens` field. This requires an approved change to `calculate_cost_usd` / `ProviderUsage`, not a measurement-only edit.

Impact if left uncorrected: configured Gemini cost is ~4× low on input, ~8.3× low on output, and additionally omits reasoning tokens; per-report cost and any check against the `< $0.15` per-report ceiling (PRD non-functional requirement) are understated.

## 5. Deterministic cost fixture (specification, for Wave B)

A cost fixture should encode the verified rates and assert:

- `cost == (prompt_tokens × input_per_m + output_billable × output_per_m) / 1e6` within $10⁻⁶ USD, where `output_billable = total_tokens − prompt_tokens`.
- A Gemini-style payload (`total > prompt + completion`) charges the residual as output.
- A Groq-style payload (`total == prompt + completion`, completion includes reasoning) is unaffected.
- Unknown usage or unknown rate returns `None` (never `0.0`, per D3-04).

## 6. Open items

1. **Gemini AI Studio pricing page** — `ai.google.dev/gemini-api/docs/pricing` transport-errored on all attempts; the $0.30/$2.50 figure is sourced from the Vertex pricing page and is consistent with the live-call behaviour. AI Studio pricing is expected to match but was not independently confirmed.
2. **Gemini 2.5 Flash lifecycle/deprecation** — Google's deprecation page (`ai.google.dev/gemini-api/docs/deprecations`) transport-errored; retirement status is unverified. The model served a live call on 2026-10-23, which rules out immediate unavailability but not a near-term deprecation notice. Confirm from primary source before Phase 4 live reliance; a near-term date triggers the ADR-034 stop rule.
3. **`usage.details` is dropped** — `parse_chat_response` maps only prompt/completion/total, so reasoning is inferred from the residual rather than read from a reported field. Recommended (Option A): a change-managed `details` passthrough in Wave B so reasoning-token accounting is explicit and auditable. An out-of-band raw provider call would violate INV-6 and is not proposed.

## 7. Source URLs

- Google Cloud Vertex AI Generative AI pricing: https://cloud.google.com/vertex-ai/generative-ai/pricing
- Groq supported models (pricing): https://console.groq.com/docs/models
- Groq model deprecations: https://console.groq.com/docs/deprecations
- Google Gemini API pricing (fetch failed): https://ai.google.dev/gemini-api/docs/pricing
- Google Gemini API deprecations (fetch failed): https://ai.google.dev/gemini-api/docs/deprecations
