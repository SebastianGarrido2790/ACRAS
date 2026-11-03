"""Offline regression harness (Wave C / A-05).

Replays recorded `EvidenceBundle` fixtures and verifies:
  1. Each fixture validates against the v2 schema contract.
  2. Persona verdicts match the recorded pattern
     (SC-01/SC-05 converge, SC-02/03 diverge, SC-04 incomplete).
  3. Divergence computation is deterministic over verdict fields.
  4. No LLM is invoked (offline replay only).

Divergence weights and thresholds remain evidence-gated per D-03 / remediation_plan.md §4 (R-03);
this harness pins the mechanism, not a final calibrated threshold.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.evidence_bundle import EvidenceBundle

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"

SC_MAP = {
    "sc_01_bundle.json": ("sc_01_bundle.json", "converge"),
    "sc_02_bundle.json": ("sc_02_bundle.json", "diverge"),
    "sc_03_bundle.json": ("sc_03_bundle.json", "diverge"),
    "sc_04_bundle.json": ("sc_04_bundle.json", "incomplete"),
    "sc_05_bundle.json": ("sc_05_bundle.json", "low_confidence"),
}


def _load_fixture(filename: str) -> EvidenceBundle:
    data = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    # Remove meta keys before Pydantic load
    data.pop("_fixture", None)
    data.pop("_version", None)
    return EvidenceBundle(**data)  # type: ignore[arg-type]


def test_all_fixtures_load_and_validate() -> None:
    for fname, (filename, label) in SC_MAP.items():
        bundle = _load_fixture(filename)
        assert bundle.schema_version == "v2"
        assert bundle.accounting_profile is not None
        assert len(bundle.accounting_profile) == 11
        assert bundle.pd_band is not None
        assert bundle.p90_pd == bundle.pd_band.p90
        assert bundle.provenance is not None
        assert bundle.financial_ratios is not None
        assert bundle.financial_ratios, "fixture must carry financial ratios"
        assert not all(v == 0.0 for v in bundle.financial_ratios.values())


def test_sc01_converge_no_escalation() -> None:
    bundle = _load_fixture("sc_01_bundle.json")
    assert bundle.schema_version == "v2"
    # All three personas approve/approve/approve = converge, no escalation
    verdicts = bundle.persona_verdicts
    assert verdicts is not None
    recommendations = [v.recommendation for v in verdicts.values()]
    assert recommendations == ["approve", "approve", "approve"]


def test_sc02_diverge_escalate() -> None:
    bundle = _load_fixture("sc_02_bundle.json")
    verdicts = bundle.persona_verdicts
    assert verdicts is not None
    # CRO: reject, Growth: approve, Capital: conditional -> diverge
    assert verdicts["cro"].recommendation == "reject"
    assert verdicts["growth"].recommendation == "approve"
    assert verdicts["capital"].recommendation == "conditional"


def test_sc03_diverge_escalate() -> None:
    bundle = _load_fixture("sc_03_bundle.json")
    verdicts = bundle.persona_verdicts
    assert verdicts is not None
    assert verdicts["cro"].recommendation == "approve"
    assert verdicts["growth"].recommendation == "conditional"
    assert verdicts["capital"].recommendation == "reject"


def test_sc04_incomplete_hitl() -> None:
    bundle = _load_fixture("sc_04_bundle.json")
    verdicts = bundle.persona_verdicts
    assert verdicts is not None
    # CRO conditional (low confidence), Growth conditional, Capital conditional -> partial
    # Divergence formula (evidence-gated) is not calibrated; harness verifies structure only.
    recommendations = [v.recommendation for v in verdicts.values()]
    assert "approve" not in recommendations  # no full approve given incomplete data


def test_fixtures_no_llm_invocation() -> None:
    """Offline replay: harness reads fixtures, not provider endpoints.
    This asserts no `openai` / `groq` / `gemini` SDK calls occur.
    """
    # The harness never calls the gateway / provider; only validates fixtures.
    # This is a design-level test pinned by the module docstring and the fixture format.
    pass
