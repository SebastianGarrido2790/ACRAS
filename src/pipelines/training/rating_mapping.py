"""PD-to-Credit-Rating Mapping Module.

Governed by:
    D-1.5 (ADR-021): Fixed illustrative PD-to-credit-rating thresholds,
        loosely inspired by public rating agency conventions, stored in params.yaml.
    PRD FR4: Convert calibrated continuous Probability of Default (PD) into
        discrete credit rating categories (e.g. AAA through CCC/C).
"""

from __future__ import annotations

from src.config.loader import RatingThreshold, load_params


def map_pd_to_credit_rating(
    pd_value: float,
    thresholds: list[RatingThreshold] | None = None,
) -> str:
    """Map a calibrated continuous probability of default to a discrete credit rating.

    DISCLAIMER & HONESTY CAVEAT (ADR-021):
    These thresholds are illustrative bands drawn loosely from public rating agency conventions.
    They do NOT represent a verified, audited, or licensed reproduction of any proprietary
    rating agency methodology (e.g. S&P, Moody's, Fitch).

    Args:
        pd_value: Probability of default in range [0.0, 1.0].
        thresholds: Optional custom list of RatingThreshold objects. If None,
            loads defaults from params.yaml.

    Returns:
        Credit rating string (e.g. 'AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC/C').

    Raises:
        ValueError: If pd_value is outside [0.0, 1.0] or thresholds list is empty.
    """
    if pd_value < 0.0 or pd_value > 1.0:
        raise ValueError(f"Probability of default must be in [0.0, 1.0], got {pd_value}")

    if thresholds is None:
        params = load_params()
        thresholds = params.rating_thresholds

    if not thresholds:
        raise ValueError("Threshold table is empty; cannot assign credit rating.")

    for item in thresholds:
        if pd_value <= item.max_pd:
            return item.rating

    return thresholds[-1].rating
