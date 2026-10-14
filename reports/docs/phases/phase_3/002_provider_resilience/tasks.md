# Tasks — 002 Provider Resilience
**Status:** ✅ Plan approved 2026-10-12; tasks unblocked except implementation authorization. Execute one task per isolated agent session; stop after each task and present diff/evidence for human approval.

- [ ] **RES-T01 Verify breaker dependency/semantics:** inspect available `pybreaker` versions and prove open/reset/half-open behavior. Satisfies RES-FR-04–06. Unblocked (plan approved); awaits implementation authorization.
- [ ] **RES-T02 Resolve policy questions:** approve 429, primary auth, malformed response, half-open scope and process-local state. Satisfies RES-FR-07–10. Answers approved — encode them in policy/tests; awaits implementation authorization.
- [ ] **RES-T03 Implement failure eligibility:** map normalized gateway errors to fallback policy; local validation errors do not retry. Satisfies RES-FR-07–10. Gateway contract approved; sequencing per GW-T03 completion.
- [ ] **RES-T04 Implement bounded orchestration:** one primary plus one fallback, approved timeouts, controlled dual failure. Satisfies RES-FR-01–03/11.
- [ ] **RES-T05 Wire independent breakers:** configure threshold/open interval/half-open behavior and transition tests. Satisfies RES-FR-04–06.
- [ ] **RES-T06 Emit routing/breaker events:** record attempts, skip/open states, transitions and final outcome. Satisfies RES-FR-12.
- [ ] **RES-T07 Prove fault/recovery matrix:** mocked timeout, connection, provider error, open/half-open/recovery, malformed output and dual failure. Satisfies RES-FR-07–13. Blocked by RES-T03–T06.
- [ ] **RES-T08 Verify non-interference/regression:** full pytest, Ruff, Pyright; EvidenceBundle v1 and deterministic Tier 1–2 outputs unchanged. Satisfies RES-FR-14. Blocked by RES-T03–T07.
