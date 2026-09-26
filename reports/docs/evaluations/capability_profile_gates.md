# Capability Profile Gates — ACRAS Tier 3 (Persona Interpretation Layer)

**Project:** ACRAS (Agentic Credit Risk & Analysis System)
**Author:** Sebastián Garrido Arévalo · **Date:** 2026-09-25 · **Status:** Completed retroactively

**Why this is retroactive, and why that's fine:** an engineering contract/gate for designing autonomous agentic AI systems needs to be completed _before_ the constitution documents specify how to build the agent. Tier 3's design already exists (`tier3_persona_architecture.md`, ADR-001 through ADR-016). This document does two things: it formalizes the answers that were already implicit in prior decisions, and — more usefully — it re-derives them independently against the template's actual questions, as a check on whether the existing design still holds up. Where it doesn't (see Gate 4), that's flagged as a real finding, not smoothed over to make the retrofit look clean.

---

## Part 1 — Pre-Build Validation Gates

### 1. Measurable Success

**Answer:** Day-one, machine-checkable success: 100% of submitted, schema-valid company profiles produce a complete, schema-valid executive report with no unhandled exception (a pure completion-rate floor). Beyond that floor, the metrics already fixed elsewhere: turnaround < 15 min (p99), cost/report < $0.15, Tier 1 calibration within documented bounds at every promotion (INV-3), and — the metric that actually validates Tier 3's reason to exist — the % of divergence-engineered golden-set cases where the three personas register a materially different verdict.

### 2. Blast Radius / Worst-Case Failure

**Answer:** The worst case isn't a rogue action — it's a human trusting a report that contains a fabricated figure or an un-escalated but genuinely contested file. Both are structurally bounded, not just discouraged: no LLM output ever becomes a calculation input (INV-1), the personas hold zero tool access and zero write access to the evidence bundle (Bounded Authority Matrix), the grounding check exists specifically to catch invented figures, and any file crossing the divergence or confidence threshold is forced to human review (INV-9) rather than auto-resolved. There is currently no autonomous external action anywhere in Tier 3.

### 3. Session Economics & Cost Ceiling

**Answer:** Ceiling: < $0.15/report (three persona calls + one deterministic convergence pass — no self-consistency multiplier). Expected value clears this trivially: the business case is collapsing a 5–10 day manual process into minutes; at real SME-lending volume, analyst-hours saved dwarf a $0.15 LLM cost by orders of magnitude. The ceiling is a discipline against scope creep (e.g., accidentally reintroducing self-consistency voting), not a genuine viability question.

### 4. Evaluation Harness

**Answer, and the one real finding from walking this gate honestly:** The golden dataset's _design_ is specified — composition (calibration edge cases + engineered-agree/engineered-diverge scenarios), size (~20–40 cases), and scoring mechanism (deterministic divergence function, LLM-as-judge grounding) — across the PRD and `tier3_persona_architecture.md`, satisfying the letter of "must be specified before building."

**But the full labeled dataset isn't scheduled to exist until Phase 5 — one phase _after_ Tier 3 (Phase 4) is built.** That means Phase 4's prompts and rubrics get built with no data-driven way to check, during development, whether the personas actually diverge the way they're designed to. The design could look right on paper and still fail the divergence-check gate at Phase 5, at which point the fix is a Phase 4 rework, not a Phase 5 tuning pass.

**Recommendation (requires your approval, not a unilateral change):** pull a small **seed set** — 3–5 hand-picked cases (one clear-converge, one or two engineered-diverge, one low-confidence/missing-data case) — forward into Phase 4 itself, used only as a build-time sanity check while writing the rubrics. The full 20–40 case set and its automated CI gating stay in Phase 5 exactly as planned. This is a Roadmap amendment, not a Phase 4 scope increase — it doesn't add a deliverable, it resequences five test cases that were going to be written anyway.

### 5. Graceful Off-Switch

**Answer:** Because Tier 3 has no side-effecting tools and no persistent cross-request state, killing a request mid-flight has no state to roll back — the failure mode is simply "no report produced," which is safe and fully recoverable by re-submitting. The practical off-switch is the circuit breaker (INV-6): a stuck or failing provider call is cut on a timeout/consecutive-error threshold and routed to fallback, not left hanging. There is no dangling side effect to clean up because nothing external was ever touched — a direct consequence of the Bounded Authority Matrix, not a separately engineered safety mechanism.

---

## Part 2 — Complexity Diagnostic

**Classification: Level 3 — Bounded Agent, at the low end of that level.**

Walking the criteria honestly, rather than assuming Level 4 because the system has multiple LLM calls:

| Level                            | Verdict for Tier 3                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Level 1 (Static Prompt)          | No — multiple calls, structured output required.                                                                                                                                                                                                                                                                                                                                                                                     |
| Level 2 (Deterministic Workflow) | **Close, but not quite.** The fan-out itself (which three calls happen, in what order) is fully fixed — the model has no say in routing or tool choice, and execution is deterministic code exactly as this level describes.                                                                                                                                                                                                         |
| **Level 3 (Bounded Agent)**      | **Best fit.** The one genuinely data-dependent branch is the convergence node's SUCCESS/ESCALATE decision, which depends strictly on what the personas returned (their divergence score) — that's the "next step depends on the previous step's output" criterion. Toolset is trivial (personas call zero tools directly). Step budget is small and fixed (4–5 steps total). Failures are low-stakes and easily reversed (§2 above). |
| Level 4 (Full Autonomous Agent)  | No — no long-horizon goal, no persistent cross-session memory, no dynamic multi-agent coordination beyond the one fixed fan-out, no large or dynamic toolset.                                                                                                                                                                                                                                                                        |

**Why this finding matters, not just as a classification exercise:** it's confirmation that the "minimal structure that controls the pain" principle (already the governing rule in `tier3_persona_architecture.md` §1) was actually followed, not just claimed. Tier 3 is closer to a deterministic workflow with one bounded decision point than to a "full autonomous agent" — which is the accurate, defensible way to describe it in an interview, not an undersell. Overclaiming Level 4 sophistication for a system that's actually Level 3 would be a worse credibility risk than the honest classification.
