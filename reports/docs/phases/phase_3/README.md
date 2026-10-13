# ACRAS Phase 3 Review Package

Draft planning artifacts only; no repository files were edited and no implementation is authorized.

Contents:
- `001_llm_gateway/`: `spec.md`, `plan.md`, `tasks.md`
- `002_provider_resilience/`: `spec.md`, `plan.md`, `tasks.md`
- `execution_plan.md`

Before approval:
1. Confirm repository SDD/module/test path conventions.
2. Resolve both specifications' clarification gates.
3. Verify Gemini primary model/endpoint and secret variable convention.
4. Review concrete gateway contract and `pybreaker` semantics.
5. Approve feature SDDs and overall Phase 3 plan explicitly.

The package reflects operator-reported qualification for Groq-direct `openai/gpt-oss-20b`, but requires revalidation at implementation time. No credentials are included.
