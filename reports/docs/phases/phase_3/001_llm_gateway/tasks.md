# Tasks — 001 LLM Gateway
**Status:** ✅ Plan approved 2026-10-12; tasks unblocked except implementation authorization. Execute one task per isolated agent session; stop after each task and present diff/evidence for human approval.

- [ ] **GW-T01 Verify baseline/layout:** inspect gateway, dependencies/lockfile, config, secret conventions, logger and test layout; record exact paths. Satisfies GW-FR-02/03/12. Unblocked (plan approved); awaits implementation authorization.
- [ ] **GW-T02 Resolve contract questions:** record decisions for Gemini endpoint, message shape, structured output, secret convention and failure representation. Satisfies GW-FR-01/05/06. Answers approved — record them in code/tests; awaits implementation authorization.
- [ ] **GW-T03 Add typed contracts:** implement approved Pydantic request/result/usage/error/event schemas and tests. Satisfies GW-FR-01/04/06/08/09.
- [ ] **GW-T04 Add config/secrets:** validate non-secret provider/model/timeouts; resolve credentials without leaking values. Satisfies GW-FR-02/03.
- [ ] **GW-T05 Implement Gemini adapter vertical slice:** normalized success/errors and mocked tests. Satisfies GW-FR-04/05/06/12.
- [ ] **GW-T06 Implement Groq adapter vertical slice:** pinned endpoint/model/env key, injected transport and tested User-Agent. Satisfies GW-FR-02/03/04/11/12. Blocked by GW-T03/T04.
- [ ] **GW-T07 Add events/cost state:** structured redacted events; unknown usage/cost remains unknown. Satisfies GW-FR-07–10.
- [ ] **GW-T08 Run acceptance/regression:** adapter/gateway tests, full pytest, Ruff, Pyright; confirm EvidenceBundle v1 and deterministic outputs unchanged. Satisfies GW-FR-12/13. Blocked by GW-T03–T07.
