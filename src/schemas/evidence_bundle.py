"""Evidence Bundle Schema Module — Version 1 (`v1`).

Governed by:
    INV-2 (ADR-002): All inter-tier and inter-agent data exchange MUST flow through
    the single, versioned Pydantic evidence-bundle schema. No tier or agent may inject
    ad hoc context outside that contract.
    ADR-014: Evidence-bundle schema versioning resolution (pre-v0-draft -> v0 -> v1 -> v2).
    D-2.4 (ADR-032): EvidenceBundle schema v1 migration — when `schema_version == "v1"`,
        Tier 1 outputs (`pd`, `credit_rating`) and Tier 2 outputs (`pd_band`,
        `financial_ratios`) are strictly required; Tier 3 `persona_verdicts` stays
        optional (`None`) to preserve tier boundary independence until Phase 4.
    PRD FR5: Persona-level interpretation depends on stable financial ratios derived
        from verified raw features.

Architectural Milestone Note (D-0.6 / ADR-014, advanced by D-2.4 / ADR-032):
    Authored in Phase 0 as the PRE-V0 DRAFT SKELETON, advanced in Phase 2 Stage 5
    to schema `v1` (Tier 2 Monte Carlo complete). The `pre-v0-draft` and `v0` tags
    are retained in the `schema_version` literal for backward compatibility with
    earlier artifacts; all new Tier 2 outputs default to `"v1"`.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Canonical discrete credit-rating categories (ADR-021 / params.yaml
#: `rating_thresholds`). Single source for v1 `credit_rating` membership checks.
VALID_CREDIT_RATINGS: frozenset[str] = frozenset(
    {"AAA", "AA", "A", "BBB", "BB", "B", "CCC/C"}
)


class PDBand(BaseModel):
    """Monte Carlo probability of default distribution percentiles (Tier 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    p10: Annotated[float, Field(ge=0.0, le=1.0, description="10th percentile PD")]
    p50: Annotated[float, Field(ge=0.0, le=1.0, description="50th percentile (median) PD")]
    p90: Annotated[float, Field(ge=0.0, le=1.0, description="90th percentile PD")]

    @model_validator(mode="after")
    def verify_percentile_monotonicity(self) -> PDBand:
        """Assert that p10 <= p50 <= p90."""
        if not (self.p10 <= self.p50 <= self.p90):
            raise ValueError(
                f"Percentiles must satisfy p10 <= p50 <= p90. "
                f"Got p10={self.p10}, p50={self.p50}, p90={self.p90}."
            )
        return self


class PersonaVerdict(BaseModel):
    """Structured evaluation verdict emitted by an interpretation persona (Tier 3).

    Governed by INV-4 & INV-8:
        Cross-persona divergence is scored deterministically over these fields.
        Persona roles are strictly CRO, Growth, and Capital.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    persona: Literal["cro", "growth", "capital"]
    # canonical: "reject" (not "decline") — enforced here for all tiers and Phase 4 prompts
    recommendation: Literal["approve", "conditional", "reject"]
    lean: Annotated[float, Field(ge=-1.0, le=1.0, description="Directional lean from -1 to 1")]
    confidence: Annotated[
        float, Field(ge=0.0, le=1.0, description="Subjective confidence in verdict")
    ]
    rationale: Annotated[str, Field(min_length=10, description="Auditable reasoning narrative")]


class EvidenceBundle(BaseModel):
    """Canonical inter-tier evidence bundle container.

    This single contract is passed sequentially through Tier 1 (ML PD), Tier 2
    (Monte Carlo simulation), and Tier 3 (Persona agents and Convergence).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Phase 0 baseline inputs
    company_id: Annotated[str, Field(min_length=1, description="Unique corporate entity ID")]
    raw_features: Annotated[
        dict[str, float | int],
        Field(description="Verified raw financial ratios from data contract validation"),
    ]
    schema_version: Literal["pre-v0-draft", "v0", "v1"] = "v1"

    # Tier 1 ML outputs (populated in Phase 1)
    pd: (
        Annotated[float, Field(ge=0.0, le=1.0, description="Calibrated Probability of Default")]
        | None
    ) = None
    credit_rating: (
        Annotated[str, Field(description="Derived rating bracket e.g. AAA, BB")] | None
    ) = None

    # Tier 2 Monte Carlo outputs (populated in Phase 2)
    pd_band: PDBand | None = None
    financial_ratios: Annotated[
        dict[str, float],
        Field(description="Derived domain financial ratios computed from raw features"),
    ] | None = None

    # Tier 3 Multi-Agent outputs (populated in Phase 4)
    persona_verdicts: Annotated[
        dict[str, PersonaVerdict],
        Field(description="Map of persona key ('cro', 'growth', 'capital') to PersonaVerdict"),
    ] | None = None

    @model_validator(mode="after")
    def enforce_v1_contract(self) -> EvidenceBundle:
        """Enforce the v1 contract for completed Tier 1 + Tier 2 outputs.

        When `schema_version == "v1"`, Tier 1 (`pd`, `credit_rating`) and Tier 2
        (`pd_band`, `financial_ratios`) outputs are strictly required. Tier 3
        `persona_verdicts` intentionally remains optional (`None` valid) to
        preserve tier boundary independence until Phase 4 (D-2.4 / ADR-032).
        `pre-v0-draft` and `v0` bundles are left permissive for backward
        compatibility with earlier-phase artifacts.
        """
        if self.schema_version != "v1":
            return self
        if self.pd is None or not math.isfinite(self.pd):
            raise ValueError("v1 bundle requires a finite `pd` in [0.0, 1.0].")
        if self.credit_rating is None or self.credit_rating not in VALID_CREDIT_RATINGS:
            raise ValueError(
                f"v1 bundle requires `credit_rating` in {sorted(VALID_CREDIT_RATINGS)}. "
                f"Got {self.credit_rating!r}."
            )
        if self.pd_band is None:
            raise ValueError("v1 bundle requires non-null `pd_band` (Tier 2 Monte Carlo output).")
        if self.financial_ratios is None or len(self.financial_ratios) == 0:
            raise ValueError("v1 bundle requires a non-empty `financial_ratios` mapping.")
        for name, value in self.financial_ratios.items():
            if not isinstance(value, float) or not math.isfinite(value):
                raise ValueError(
                    f"v1 `financial_ratios[{name!r}]` must be a finite float. Got {value!r}."
                )
        return self
