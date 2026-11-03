# Phase 4 — Stage 1 Record (Evidence Contract & Seed-Case Integrity)

**Date:** 2026-11-03
**Stage:** 1 — P4-01. Tasks T3-T02 … T3-T05.
**Status:** Implementation complete and verified. **Gate 1 passed 2026-11-03** after owner acceptance of ADR-016.

---

## 1. Contract change (T3-FR-01 / T3-FR-03 / T3-FR-04)

`src/schemas/evidence_bundle.py`:

| Addition | Type | Default | Semantics |
| --- | --- | --- | --- |
| `EvidenceBundle.covenant_flags` | `list[str] \| None` | `None` | `None` = not available; never `[]` |
| `EvidenceBundle.revenue_growth_rate` | `float \| None` | `None` | `None` = not available; never `0.0` |
| `EvidenceBundle.pipeline_value_estimate` | `float \| None` | `None` | `None` = not available; never `0.0` |
| `EvidenceBundle.concentration_flag` | `bool \| None` | `None` | `None` = not available; never `False` |
| `PersonaVerdict.limitations` | `list[str]` | `default_factory=list` | Verbatim evidence gaps; empty when none |

Unchanged: `schema_version` literal (still includes `"v2"`; no `v3`), `extra="forbid"`,
`frozen=True`, `p90_pd` computed from `pd_band.p90`, v1 validation, and Tier 1/Tier 2
behavior. No existing field changed meaning.

## 2. Provenance rules (T3-FR-02)

`DEFINED_DERIVATIONS = {"financial_ratios", "p90_pd"}`.

1. Every provenance entry tagged `synthetic` must have a non-empty key in
   `synthetic_assumptions`. This now covers all six tags, not just three; notably the
   newly typed `concentration_flag`.
2. `derived` is rejected unless it is `financial_ratios` (equal to
   `compute_financial_ratios(accounting_profile)`) or `p90_pd` (equal to
   `pd_band.p90`).
3. No cross-field requirement makes a missing Tier 3 value an error: absence remains
   `None` and the persona records a limitation (T3-FR-08, Stage 3).

## 3. Seed-case mapping (T3-FR-01 / T3-FR-02, Q-3)

All four fields are populated from evidence already in the fixture or from an explicit
tagged-synthetic assumption. No persona verdict and no financial ratio was rewritten.

| Case | Field | Value | Provenance | Source / assumption |
| --- | --- | --- | --- | --- |
| SC-01 | `covenant_flags` | `[]` | synthetic | profile-supplied; no covenant breach |
| SC-01 | `revenue_growth_rate` | `0.10` | synthetic | assumed +10% YoY from profile; not observed |
| SC-01 | `pipeline_value_estimate` | `250000.0` | synthetic | deal-level synthetic; moderate pipeline |
| SC-01 | `concentration_flag` | `false` | synthetic | profile-supplied; no customer concentration |
| SC-02 | `covenant_flags` | `["covenant_breach_indicator"]` | synthetic | profile-supplied; covenant breach indicator present |
| SC-02 | `revenue_growth_rate` | `0.35` | synthetic | assumed +35% YoY from profile; not observed |
| SC-02 | `pipeline_value_estimate` | `750000.0` | synthetic | high deal pipeline (growth driver) |
| SC-02 | `concentration_flag` | `false` | synthetic | profile-supplied; no customer concentration |
| SC-03 | `covenant_flags` | `[]` | synthetic | profile-supplied; no covenant breach |
| SC-03 | `revenue_growth_rate` | `0.06` | synthetic | assumed +6% YoY from profile; not observed |
| SC-03 | `pipeline_value_estimate` | `300000.0` | synthetic | moderate deal pipeline |
| SC-03 | `concentration_flag` | `true` | synthetic | profile-supplied; top customer 60% of revenue |
| SC-04 | `covenant_flags` | `null` | synthetic | profile-supplied; incomplete information - missing covenant history |
| SC-04 | `revenue_growth_rate` | `null` | synthetic | no source supplied; value stays `None` |
| SC-04 | `pipeline_value_estimate` | `null` | synthetic | no source supplied; value stays `None` |
| SC-04 | `concentration_flag` | `null` | synthetic | no source supplied; value stays `None` |
| SC-05 | `covenant_flags` | `[]` | synthetic | profile-supplied; no covenant breach |
| SC-05 | `revenue_growth_rate` | `0.08` | synthetic | assumed +8% YoY from profile; not observed |
| SC-05 | `pipeline_value_estimate` | `200000.0` | synthetic | deal-level synthetic; moderate pipeline |
| SC-05 | `concentration_flag` | `false` | synthetic | profile-supplied; no customer concentration |

`financial_ratios` and `p90_pd` remain `derived` in every fixture and satisfy their
defined derivation. `tail_loss_estimate` and `capital_consumption_estimate` remain absent.

## 4. Seed-case repairs (Q-1(b) / Q-3)

| Case | Change | Reason |
| --- | --- | --- |
| SC-01 | `pd` 0.015 → 0.010, `credit_rating` AAA → BBB, band 0.010/0.015/0.025 → 0.008/0.010/0.012 | Rating was incoherent (`pd = 0.015` maps to BBB, inclusive). Moving `pd` to the BBB bucket center makes the case coherent **and** high-confidence: proxy A 0.80, proxy B 1.00. Verdicts and ratios unchanged. |
| SC-03 | `credit_rating` BBB → BB | Latent second incoherence found by the integrity test: `pd = 0.025` maps to BB. Single-label fix; PD, band, verdicts, and ratios unchanged. |
| SC-04 | `_fixture` label → "persona-level incomplete evidence (typed fields None, conditional verdicts, HITL)" | Previous label conflated persona-level gaps with low Tier 1 confidence and claimed a missing persona although three verdicts are present. Verdicts unchanged; all four Tier 3 fields stay `None`. |
| SC-05 | New fixture `tests/fixtures/sc_05_bundle.json` | Genuine low-Tier-1-confidence case for the Stage 2 selection check: `pd = 0.0145` near the BBB/BB boundary, band 0.005/0.0145/0.050. Personas converge (all approve) so escalation is driven by Tier 1 confidence, not divergence. |

Post-repair Q-1 arithmetic (pre-registered for Stage 2; thresholds stay provisional):

| Case | pd | p10/p50/p90 | Proxy A | Proxy B | Role |
| --- | --- | --- | --- | --- | --- |
| SC-01 | 0.0100 | 0.008/0.010/0.012 | 0.800 | 1.000 | converge / high confidence |
| SC-02 | 0.0450 | 0.030/0.045/0.080 | 0.444 | 0.286 | diverge |
| SC-03 | 0.0250 | 0.015/0.025/0.045 | 0.400 | 0.571 | diverge |
| SC-04 | 0.0650 | 0.045/0.065/0.100 | 0.577 | 0.300 | persona-level incomplete |
| SC-05 | 0.0145 | 0.005/0.0145/0.050 | 0.000 | 0.100 | low Tier 1 confidence |

At the provisional threshold `0.30`, proxy B separates SC-05 (0.100) from SC-01 (1.000);
proxy A still cannot. Stage 2 performs and records the formal selection.

## 5. ADR-016

Written in `reports/docs/architecture/system_design.md` §6 (after ADR-015), replacing the
former reserved-note placeholder. It records: additive v2 change, the four fields and
`limitations`, `None` semantics, the narrowed provenance rules, the excluded loss fields,
and supersession of the §7 version-bump expectation (no `v3`). The §7 bullet is closed
and points to ADR-016.

**Owner acceptance:** recorded 2026-11-03. ADR-016 is accepted; Gate 1 closed.

## 6. Falsification (D-01)

Mutation: `revenue_growth_rate` default changed from `None` to `0.0`.

```text
uv run pytest tests/unit/test_contract_fields.py::test_absent_fields_preserve_none \
  tests/unit/test_fixture_integrity.py::test_tier3_fields_populated_except_the_incomplete_case -q

FAILED test_contract_fields.py::test_absent_fields_preserve_none
E   AssertionError: assert 0.0 is None
1 failed, 1 passed
```

Restored the default to `None`; the same test passes again (included in the green runs
below). The fixture-integrity check alone does not catch the coercion because SC-04
explicitly passes `null`; the contract test is the guard.

## 7. Verification

| Check | Result |
| --- | --- |
| New tests | `tests/unit/test_contract_fields.py` (9) + `tests/unit/test_fixture_integrity.py` (10, incl. 5 parametrized cases) = 19 |
| Targeted contract/fixture/schema run | 29 passed |
| Full suite | `uv run pytest -q`: **252 passed, 5 skipped**, 71 warnings, 85.04 s, exit 0 (final pre-push run) |
| Ruff | `uv run ruff check .`: 0 findings, exit 0 |
| Pyright | `uv run pyright`: 0 errors, 0 warnings, exit 0 |
| Post-suite tree | only intended Stage 1 files modified/untracked |
| v1 / Tier 1 / Tier 2 | unchanged; existing 233 tests still green |
| Offline harness | now loads SC-01 … SC-05; no LLM invocation |

## 8. Gate 1 assessment

| Gate condition | Evidence |
| --- | --- |
| All contract tests pass | 19 new checks green; full suite green |
| `None` is preserved | `test_absent_fields_preserve_none`, plus falsification above |
| Seed cases validate and are internally consistent | `test_fixture_integrity.py`: completeness, rating↔PD mapping, defined derivations, synthetic assumptions, `p90_pd` |
| ADR-016 accepted | Accepted by the owner 2026-11-03 |
| v1 and Tier 1/Tier 2 unchanged | v1 contract test + full-suite regression |

No commit or push had been performed when this record was written; both were later authorized by the owner on 2026-11-03.
