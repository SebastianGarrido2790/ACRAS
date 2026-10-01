"""PD-to-Credit-Rating Mapping Module.

Governed by:
    D-1.5 (ADR-021): Fixed illustrative PD-to-credit-rating thresholds,
        loosely inspired by public rating agency conventions, stored in params.yaml.
    PRD FR4: Convert calibrated continuous Probability of Default (PD) into
        discrete credit rating categories (e.g. AAA through CCC/C).
"""

from __future__ import annotations

from src.tier1_ml.rating import map_pd_to_credit_rating

__all__ = ["map_pd_to_credit_rating"]

