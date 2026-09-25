# Tier 3 Persona Architecture — Design & Pattern Justification

**Project:** ACRAS: Hybrid Agentic MLOps System for Credit Risk
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-29 · **Status:** Design proposal — extends the planning set, precedes Stage 6

This document does two things: it justifies, explicitly and against named alternatives, why Tier 3 is built the way it is — and it specifies enough of the persona rubrics, evidence-bundle fields, and `PersonaVerdict` schema for Stage 6 to draft a complete evidence-bundle skeleton, without writing any prompt text or graph-wiring code, both of which correctly wait for Phase 4.

---

## 1. Why This Pattern, Not Another

**The governing rule, applied literally:** _first identify the pain, then choose the minimal structure that controls it_ — not "I want a multi-agent system, how do I build one."

**The pain:** interpreting a risk distribution requires applying three genuinely different, genuinely conflicting business mandates — risk exposure, growth appetite, cost of capital — to the same set of facts, and preserving _where they disagree_ rather than collapsing to one blended answer.

**Running the actual decision tree against Tier 3:**

| Question                                                   | Answer for ACRAS                                                                                                                                                                                                                                      |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Is the task complex?                                       | Yes — three distinct interpretive mandates over one evidence set.                                                                                                                                                                                     |
| Does it need specialization?                               | Yes — each mandate weighs different evidence differently (§3).                                                                                                                                                                                        |
| Does it need distinct authority?                           | No — all three personas have identical, read-only access. This is fine; not every pillar has to fire.                                                                                                                                                 |
| Does it need independence, parallelism, or risk isolation? | Yes to parallelism (three calls run concurrently, not in sequence) and risk isolation (one persona's degenerate output can't corrupt the others). **Partial, deliberately, on independence** — see the epistemological-independence discussion below. |

Three of the five justification pillars fire cleanly. That's the actual answer to "why multi-agent here": not "multi-agent is more sophisticated," but a specific, named pain (conflicting expert domains) that a single agent structurally cannot represent, because a single agent producing "three perspectives" in one pass is a formatting instruction, not three independent readings.

### Why not the alternatives

- **Single agent, one summarizing call.** Rejected — this is the exact case the Merging Test rules out. Merging the three personas into one call loses the thing Tier 3 exists to produce: the disagreement signal. A single model asked to "consider three perspectives" tends to produce three stylistically-varied paragraphs that agree with each other far more than genuinely conflicting mandates should — because there's no structural pressure forcing the divergence, only a prompt instruction asking for it.
- **Sequential Plan-and-Execute across the three mandates.** Rejected — nothing about CRO's, Growth's, and Capital's readings depends on each other's output; sequencing them would only add latency and, worse, let an earlier persona's framing leak into a later one's reasoning through shared conversation history, which is a real known failure mode: it correlates outputs that are supposed to be independent.
- **Competitive/debate pattern** (personas argue, attempt to falsify each other's claims). Rejected — that pattern is for _auditing_, where an evaluator needs to try to break a claim. Tier 3's personas aren't auditing each other; they're applying different mandates to facts that are already validated upstream (INV-2, INV-7). A debate loop would add multi-turn cost and drift risk to solve a problem ACRAS doesn't have.
- **Full independent-auditor pattern** (each persona gathers its own evidence, `Evidence_persona_A ≠ Evidence_persona_B`). Rejected, and worth being explicit about why: this is the _strong_ form of epistemological independence, and it's the right tool when the goal is catching a producer's error. That isn't Tier 3's goal. Tier 3's goal is three honest, different interpretations of one already-trustworthy fact set. Forcing independent evidence-gathering here would just mean three personas working from three inconsistent views of the same company, which produces confusion, not decision value.

**What Tier 3 actually claims, precisely:** it satisfies the _weak_ form of epistemological independence — `Evaluation process ≠ Generation process` — because the convergence node that decides SUCCESS/ESCALATE is a deterministic function (ADR-004), never another LLM call re-judging the personas' prose. It does not claim the strong form (independent evidence per persona), because that would solve a different problem than the one Tier 3 has.

### Surviving the standard case against multi-agent

Two real warnings apply here, and Tier 3 has to survive both, not just cite the pillars and move on:

**"The median multi-agent system underperforms a single capable model."** True, and the reason is usually coordination overhead and compounding drift from multi-turn negotiation between agents. Tier 3 doesn't have that shape — it's three single-shot, parallel calls into one deterministic reconciliation function, not a back-and-forth. The "coordination cost" is one shared JSON schema, not a conversation.

**Is this "theatrical multi-agent"?** Running the actual checklist: same model across personas? Yes — and that's fine, because divergence here is deliberately engineered through rubric and derived-field differences (ADR-005), not through model diversity. Same context? Yes, by design — see the independence discussion above; this is a disclosed, justified departure, not an oversight. Same authority? Yes — appropriate, since none of them execute actions. Identical tasks? **No** — this is the pillar that actually matters, and it's real: each persona is instructed to weigh different fields toward a different objective function, not to restate the same analysis in a different voice. Independent validation? Yes — the convergence node is a separate, non-generating component, structurally incapable of being the same self-confirming loop as "the analyst grades its own work."

---

## 2. Where Tier 3 Sits in the Governed Architecture

Already established and unchanged by this document: Router (trivial pass-through) → Planner (deterministic Tier 1→2 pipeline) → **Workers** (Data Scientist Agent, Financial/Domain Analyst Agent, and the three personas — this document specifies the persona Workers in detail) → **Evaluator** (the convergence node) → SUCCESS / RETRY / STOP / ESCALATE.

---

## 3. The Persona Rubrics

Each persona is a bounded Worker: it produces a result and evidence: it does not validate its own output, and it does not see the other personas' output before emitting its own.

| Persona     | Mandate                         | Primary weighted evidence                        | Can do                                     | Cannot do                                                        |
| ----------- | ------------------------------- | ------------------------------------------------ | ------------------------------------------ | ---------------------------------------------------------------- |
| **CRO**     | Tail-risk exposure              | P90 loss band, covenant/qualitative risk flags   | Read the evidence bundle, emit one verdict | Call any tool, see the other personas' output, modify the bundle |
| **Growth**  | Commercial/relationship value   | Revenue growth rate, pipeline/relationship value | Same as above                              | Same as above                                                    |
| **Capital** | Cost of capital / concentration | Capital-consumption estimate, concentration flag | Same as above                              | Same as above                                                    |

This is the concrete mechanism behind ADR-005's "role-specific derived fields": each persona's prompt foregrounds a different pre-computed field from the _same_ evidence bundle. None of these derived fields are computed by the persona itself — they're deterministic outputs of the Financial/Domain Analyst Agent or Tier 2, consistent with INV-1.

---

## 4. Evidence-Bundle Field Additions (for Stage 6)

Stage 6 drafts the pre-v0 skeleton with `Optional[...]` placeholders for "everything later tiers add." This is the concrete field list Tier 3 needs, so Stage 6 doesn't have to guess:

```text
tail_loss_estimate: Optional[float]           # derived from P90 band — CRO's primary field
covenant_flags: Optional[list[str]]           # qualitative risk flags — CRO
revenue_growth_rate: Optional[float]          # Growth's primary field
pipeline_value_estimate: Optional[float]      # Growth
capital_consumption_estimate: Optional[float] # Capital's primary field
concentration_flag: Optional[bool]            # Capital
```

All six are `None` until Tier 2 / the Financial/Domain Analyst Agent populate them — no change to the pre-v0/v0 versioning resolution already decided (D-0.6). They're additions to the _field list_, not a change to _when_ the schema formally becomes "v0."

---

## 5. The `PersonaVerdict` Schema, Refined

One addition beyond what's in `system_design.md`'s ADR-004 sketch: a `limitations` field, so a persona can flag genuine evidentiary gaps as structured data rather than burying a hedge inside free-text rationale where nothing downstream can act on it.

```python
class PersonaVerdict(BaseModel):
    persona: Literal["cro", "growth", "capital"]
    recommendation: Literal["approve", "conditional", "decline"]
    lean: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list)
    rationale: str
```

**A heavier alternative considered and rejected:** a full inter-agent message envelope (`task_id`, `sender`, `receiver`, `constraints`, `authority`, `evidence_requirements`) — the kind of protocol that matters when agents dynamically delegate tasks to each other. Tier 3 doesn't do that: it's a fixed fan-out from one evidence bundle to three known recipients, not a dynamic delegation network. Adopting the full envelope here would be exactly the kind of unnecessary structure the governing rule warns against — it doesn't control a pain Tier 3 actually has.

---

## 6. Structured Output: Constrained Decoding, Not "Ask Nicely"

`PersonaVerdict` must be enforced via constrained/schema-forced decoding (native structured-output enforcement, not a prompt instruction asking for JSON). Two weaker alternatives are explicitly rejected as the _primary_ mechanism:

- **Prompting for JSON compliance** — unreliable at scale; occasional conversational filler breaks parsers.
- **Retry-on-parse-failure as the primary mechanism** — adds latency and token cost per failure and still doesn't guarantee compliance on the retry.

Retry logic still exists, but only as a fallback for a constrained-decoding failure, which should be rare — and per the Observable State Machine already defined (`persona_verdict_schema_invalid AND retries < max_retries`), a fallback retry firing at all is itself worth logging as a signal, not silently absorbed.

---

## 7. Context Isolation Per Persona

Each persona node receives its own isolated context: the evidence bundle plus its own rubric — never the other two personas' prompts, outputs, or the raw evidence-gathering trace. This is the structural difference between a genuine fan-out and the single most common way multi-agent systems quietly degrade into theater: asking one model, in one context window, to "consider three perspectives" is a formatting instruction, not three independent Workers. Isolation is what makes "the three personas didn't see each other's answer" a provable architectural fact instead of an assumption about prompt discipline.

---

## 8. The Convergence Node

**Inputs:** three `PersonaVerdict` objects.
**Process:** the deterministic divergence function already fixed by ADR-004 (categorical mismatch across `recommendation` + variance of `lean`).
**Decision:**

```text
SUCCESS   IF divergence_score < threshold AND all verdicts schema-valid
ESCALATE  IF divergence_score >= threshold OR tier1_confidence < confidence_threshold
RETRY     IF a verdict failed schema validation AND retries < max_retries
STOP      IF retries exhausted OR per-report cost cap exceeded
```

Every branch is an observable, provable condition — never "the system considers the report complete." This is the same discipline already applied everywhere else in this project, restated here as Tier 3's specific instance of it.

---

## 9. Security Notes Specific to Tier 3

Extends `AGENTS.md` §8 rather than duplicating it — only what's specific to this layer:

- **Validator Sandwich, applied to Tier 3 specifically:** Input Guardrail = evidence-bundle schema validation (already enforced upstream); Stochastic Policy = the persona LLM call; Output Guardrail = `PersonaVerdict` schema validation, then the grounding check.
- **Derived fields are still untrusted until validated.** Even though they come from ACRAS's own deterministic layer, not an external source, they cross a component boundary into the persona's prompt — the same schema-validation discipline applies, not a weaker one just because the source is internal.
- **Cost profile is intentionally not a self-consistency ensemble.** Three parallel calls plus one deterministic convergence pass — not N=4–8 repeated sampling per persona. Confusing "three specialized personas" with "self-consistency voting" would silently multiply the per-report cost ceiling (already under real scrutiny in the Charter) for a property Tier 3 isn't trying to buy.

---

## 10. What Still Waits for Phase 4

Unchanged from the earlier decision: exact prompt text and few-shot examples, the actual LangGraph node/edge wiring, and the divergence-threshold's real numeric value (still pending Phase 5's golden-set calibration). This document fixes the _architecture and contracts_; Phase 4 fixes the _wording and code_.

---

## Note for Stage 6 / Future ADR

If approved, the `limitations` field addition to `PersonaVerdict` and the six evidence-bundle fields in §4 should be folded into `system_design.md` as a new ADR entry (ADR-016) when Stage 6 or Phase 4 formalizes the schema — consistent with how every other decision in this project has been logged at the point it's actually implemented, not before.
