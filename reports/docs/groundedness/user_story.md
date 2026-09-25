# User Story & Problem Framing — ACRAS (Agentic Credit Risk & Analysis System)

**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-28 · **Version:** 2.0

---

## Document Overview

- **What it is:** A user-centered requirements document detailing core stakeholder personas (Credit Analyst, Head of Credit Risk, Growth Lead), root-cause analysis (5 Whys), Jobs-to-be-Done (JTBD), failure modes, and user journey maps.
- **Why it exists:** Connects technical system capabilities to real-world credit committee dynamics, ensuring that the multi-agent system addresses authentic user bottlenecks, defensibility requirements, and operational tensions.
- **How to use it:** Use this document when designing agent personas, prompt rubrics, UI dashboards, and human-in-the-loop escalation paths to ensure alignment with user needs.

---

## Personas & Stories

### Ana — SME Credit Analyst (Primary / day-to-day operator)

1. As a Credit Analyst, I want to submit a company's financials and receive a full risk report within minutes, so that I can close my analysis queue the same day instead of carrying a file for a week.
2. As a Credit Analyst, I want to see exactly which inputs and calculations produced the recommendation, so that I can defend it to a client or auditor without redoing the analysis myself.

### Rodrigo — Head of Credit Risk / CRO (Secondary / approver-oversight)

1. As Head of Credit Risk, I want files where the risk, growth, and capital perspectives materially disagree to be flagged for my review, so that judgment calls aren't silently resolved by an averaging heuristic I never see.
2. As Head of Credit Risk, I want every model version and its calibration metrics logged and versioned, so that I can show an auditor that today's decisions were made on a validated, in-spec model.

### Marcela — Commercial / Growth Lead (Secondary / deal originator)

1. As a Commercial Lead, I want same-day risk turnaround on new SME opportunities, so that I don't lose deals to a competitor who can quote faster.
2. As a Commercial Lead, I want a clear, specific reason when a deal is declined or downgraded, so that I can return to the client with an actionable path (e.g., collateral, shorter term) instead of a bare rejection.

## The 5 Whys (Root Cause Analysis)

1. **Why does an SME file take 5–10 days?** Because one analyst manually gathers, cross-references, and writes up financials, bureau data, and qualitative notes sequentially.
2. **Why is it manual and sequential?** Because no tooling exists that computes the quantitative score and generates the committee-style interpretive narrative in a single pass.
3. **Why hasn't that tooling existed?** Because an ML model alone produces a number without judgment, and a generic LLM summarizer can't be trusted with the number itself — most shops don't fully trust either to operate unsupervised.
4. **Why has no one combined them safely?** Because doing so requires an architecture where the LLM is structurally prevented from inventing or altering the numeric output. Most implementations either bolt an LLM onto a spreadsheet (unsafe) or keep a purely quantitative model (uninterpretable) rather than architecting a hard boundary between the two.
5. **Why does that boundary matter enough to build deliberately?** Because without it, a lender either accepts slow, human-bottlenecked underwriting, or fast underwriting it can't defend to a regulator or committee. The real root cause is the absence of a system that treats deterministic computation and interpretive judgment as two different failure domains requiring two different guarantees.

## Jobs-to-be-Done

- _When_ I receive a new SME loan file, _I want to_ get a defensible, committee-quality risk read quickly, _so I can_ move the deal forward or decline it without a week of back-office work.
- _When_ I have to justify a lending decision to a regulator or my own risk committee, _I want to_ point to a specific, reproducible computation and a documented rationale, _so I'm_ not defending a gut call.
- _When_ my own risk and growth instincts about a deal conflict, _I want_ that conflict named explicitly, _so I_ make the trade-off deliberately, not by accident.

## Problem Statement (User Perspective)

Every persona above has a different day-to-day pain, but it converges on one complaint: the current process forces a choice between speed and defensibility. Users can get a fast answer or a defensible one, not both — and there is no visibility into where their own risk/growth intuition would agree or disagree with the numbers until deep into the file.

## Failure Mode Analysis (What Breaks Without This System)

- Without the Tier 2 distribution, an analyst underwrites off a single, potentially misleading PD point estimate near a decision boundary and misses tail-risk exposure entirely.
- Without parallel Tier 3 interpretation, analysis collapses to whichever single reviewer writes the memo, silently omitting the risk/growth/capital tension a real committee would surface.
- Without the calibration gate, a model that "looks fine" on AUC could systematically over- or under-state actual default probability, undetected until realized losses diverge from expectation months later.
- Without the divergence check, the system could ship with three agents that always agree, creating false confidence that a "committee" reviewed the file when one opinion was effectively rubber-stamped three times.
- Without HITL escalation, a marginal, contested file gets auto-resolved by whatever tie-breaking logic exists, removing the human judgment step regulators expect on contestable decisions.

## User Journey Map

**Current state (manual):**
Analyst requests financials & bureau report → manually computes ratios → cross-references credit history → drafts a recommendation memo → reviewer/committee reads it and asks follow-ups → recommendation finalized. **Elapsed: 5–10 days.**

**Future state (with ACRAS):**
Analyst enters a company profile in the dashboard → Tier 1 returns a PD in seconds → Tier 2 expands it into a risk distribution → Tier 3 personas independently interpret the same evidence in parallel → the convergence node synthesizes agreement or flags disagreement for HITL → analyst receives the full report, decision-ready or escalated, with a complete computation/reasoning trace attached for audit. **Elapsed: minutes.**

## Constraints Acknowledged by Users

- The system's output is a recommendation, not a binding approval — final sign-off stays human, especially on flagged or escalated files.
- The model is trained on structured financial data; on companies with materially incomplete records, the system flags low confidence rather than forcing a rating.
- A "divergence" flag will sometimes reflect genuine ambiguity in the case rather than a system defect — that is the intended behavior, not noise to be tuned away.
