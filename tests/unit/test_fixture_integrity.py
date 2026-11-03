"""Seed-case integrity checks (P4-01 / Stage 1 gate).

The seed fixtures are the evidence Tier 3 personas read. This module proves the
set is complete and internally coherent: `credit_rating` matches the
deterministic PD mapping, every `derived` provenance tag names a defined
derivation, and every `synthetic` tag carries an assumption entry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.schemas.evidence_bundle import DEFINED_DERIVATIONS, EvidenceBundle
from src.tier1_ml.rating import map_pd_to_credit_rating
from src.tier2_simulation.ratios import compute_financial_ratios

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
SEED_CASES = {f"sc_0{i}_bundle.json" for i in range(1, 6)}


def _fixture_paths() -> list[Path]:
    return sorted(FIXTURE_DIR.glob("sc_0*_bundle.json"))


def _load(path: Path) -> tuple[EvidenceBundle, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("_fixture", None)
    data.pop("_version", None)
    return EvidenceBundle(**data), data


def test_seed_case_set_is_complete() -> None:
    """SC-01 … SC-05 are all present (Q-1(b) adds the low-confidence case)."""
    assert {path.name for path in _fixture_paths()} == SEED_CASES


def test_credit_rating_matches_deterministic_pd_mapping() -> None:
    """A fixture's rating must be the rating Tier 1 would assign to its PD."""
    for path in _fixture_paths():
        bundle, _ = _load(path)
        assert bundle.pd is not None, path.name
        assert bundle.credit_rating == map_pd_to_credit_rating(bundle.pd), path.name


def test_derived_tags_have_defined_derivations() -> None:
    """`derived` is only legal for fields the v2 contract actually derives."""
    for path in _fixture_paths():
        bundle, _ = _load(path)
        assert bundle.provenance is not None, path.name
        for field, tag in bundle.provenance.items():
            if tag != "derived":
                continue
            assert field in DEFINED_DERIVATIONS, f"{path.name}: {field} tagged derived"
            if field == "financial_ratios":
                assert bundle.financial_ratios is not None, path.name
                assert bundle.accounting_profile is not None, path.name
                assert bundle.financial_ratios == compute_financial_ratios(
                    bundle.accounting_profile
                ), path.name
            elif field == "p90_pd":
                assert bundle.pd_band is not None, path.name
                assert bundle.p90_pd == bundle.pd_band.p90, path.name


def test_synthetic_tags_have_assumptions() -> None:
    """Every `synthetic` tag maps to an explicit assumption string."""
    for path in _fixture_paths():
        bundle, _ = _load(path)
        assert bundle.provenance is not None, path.name
        assert bundle.synthetic_assumptions is not None, path.name
        synthetic = {k for k, v in bundle.provenance.items() if v == "synthetic"}
        assert synthetic <= set(bundle.synthetic_assumptions), path.name
        for field in synthetic:
            assert bundle.synthetic_assumptions[field].strip(), f"{path.name}: {field}"


def test_tier3_fields_populated_except_the_incomplete_case() -> None:
    """SC-01/02/03/05 carry values; SC-04 preserves `None` for missing evidence."""
    fields = (
        "covenant_flags",
        "revenue_growth_rate",
        "pipeline_value_estimate",
        "concentration_flag",
    )
    for path in _fixture_paths():
        bundle, _ = _load(path)
        values = [getattr(bundle, field) for field in fields]
        if path.name == "sc_04_bundle.json":
            assert all(value is None for value in values), path.name
        else:
            assert all(value is not None for value in values), path.name


@pytest.mark.parametrize("case", sorted(SEED_CASES))
def test_fixture_contract_metadata(case: str) -> None:
    """Every seed bundle is v2 with a coherent, computed `p90_pd`."""
    bundle, _ = _load(FIXTURE_DIR / case)
    assert bundle.schema_version == "v2"
    assert bundle.p90_pd is not None
    assert bundle.pd_band is not None
    assert bundle.p90_pd == bundle.pd_band.p90
