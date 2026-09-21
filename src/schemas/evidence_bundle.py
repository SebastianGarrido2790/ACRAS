"""Evidence Bundle Schema Module — Pre-v0 Draft Skeleton.

Governed by:
    INV-2 (ADR-002): All inter-tier and inter-agent data exchange MUST flow through
    the single, versioned Pydantic evidence-bundle schema. No tier or agent may inject
    ad hoc context outside that contract.
    ADR-014: Evidence-bundle schema versioning resolution.

Architectural Milestone Note (D-0.6 / ADR-014):
    This module represents the PRE-V0 DRAFT SKELETON authored during Phase 0.
    Formal schema versioning begins at Tier 1 (schema v0), when the frozen ML model
    populates the calibrated Probability of Default (PD). Subsequent tiers advance
    the contract (Tier 2 Monte Carlo -> v1; Tier 3 Agent Verdicts -> v2).

    All fields belonging to downstream Tiers 1–3 are explicitly typed here with
    sensible sub-models but default to `None`, ensuring that Phase 0 can instantiate
    and validate the initial contract without requiring later tiers to exist yet.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    schema_version: Literal["pre-v0-draft"] = "pre-v0-draft"

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
