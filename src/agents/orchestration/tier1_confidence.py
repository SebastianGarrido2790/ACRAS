"""Pure Tier 1 confidence proxies for the Tier 3 convergence core (P4-03).

Governed by:
    T3-FR-12: both proxies are implemented as pure functions of Tier 1/Tier 2
        outputs only; Phase 4 selects one by the approved bounded check and the
        other stays implemented and documented.
    `plan.md` §3.2: proxy A (band dispersion) and proxy B (rating-boundary
        margin) with their normalizers and edge cases.
    D4-02/D4-03: thresholds and the selected proxy are configuration values
        (`tier3:` in `params.yaml`), provisional until Phase 5 calibration.

Both proxies return a value in `[0, 1]` where higher means more confidence in
the Tier 1 output. Missing required inputs fail safe to `0.0`: absence of
evidence is never treated as high confidence.

The module is pure: no I/O, gateway, network, or model call.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.config.loader import RatingThreshold
    from src.schemas.evidence_bundle import EvidenceBundle, PDBand

#: Configuration literals for `tier3.tier1_confidence_proxy`.
ConfidenceProxy = Literal["band_dispersion", "rating_boundary_margin"]
PROXY_BAND_DISPERSION: ConfidenceProxy = "band_dispersion"
PROXY_RATING_BOUNDARY_MARGIN: ConfidenceProxy = "rating_boundary_margin"


def band_dispersion_confidence(pd_band: PDBand, *, reference_width: float) -> float:
    """Return proxy A: confidence from the relative width of the PD band.

    Formula (`plan.md` §3.2):

    `1 - min(1, ((p90 - p10) / p50) / reference_width)`

    A narrower band relative to the median implies a more stable Tier 1
    estimate. `p50 <= 0` returns `0.0` because the relative width is undefined;
    an undefined width is not high confidence.

    Args:
        pd_band: Tier 2 percentile band (`p10 <= p50 <= p90`, each in `[0, 1]`).
        reference_width: Positive normalizer (`tier3.band_dispersion_ref`).

    Returns:
        Confidence in `[0, 1]`.

    Raises:
        ValueError: If `reference_width` is not a finite positive number.
    """
    if not math.isfinite(reference_width) or reference_width <= 0.0:
        raise ValueError(
            f"band_dispersion_ref must be finite and > 0.0; got {reference_width!r}."
        )
    if pd_band.p50 <= 0.0:
        return 0.0

    relative_width = (pd_band.p90 - pd_band.p10) / pd_band.p50
    return _clamp_unit(1.0 - min(1.0, relative_width / reference_width))


def rating_boundary_margin_confidence(
    pd: float,
    thresholds: Sequence[RatingThreshold],
) -> float:
    """Return proxy B: confidence from distance to the nearest rating boundary.

    The bucket containing `pd` has finite bounds `[L, U]`. The score is
    `min(1, min(pd - L, U - pd) / ((U - L) / 2))`: `0.0` exactly on a boundary
    and `1.0` at the bucket center, so a PD near a rating cut-off is treated as
    decision-unstable.

    The lowest and highest buckets are nominally open-ended. They use their one
    finite boundary and normalize by the nearest finite bucket's half-width
    (the AAA bucket by the AA half-width, the CCC/C bucket by the B half-width).

    Out-of-range or non-finite `pd` returns `0.0` (fail-safe); it never raises
    for data that passed the bundle contract but sits outside the configured
    table.

    Args:
        pd: Calibrated probability of default.
        thresholds: Ascending rating brackets from `params.yaml`
            (`pd <= max_pd` selects the bucket).

    Returns:
        Confidence in `[0, 1]`.

    Raises:
        ValueError: If the threshold table is malformed (fewer than two
            brackets, non-finite/out-of-range bounds, or non-increasing bounds).
    """
    if not math.isfinite(pd) or pd < 0.0 or pd > 1.0:
        return 0.0

    _validate_thresholds(thresholds)

    bucket_index: int | None = None
    for index, threshold in enumerate(thresholds):
        if pd <= threshold.max_pd:
            bucket_index = index
            break
    if bucket_index is None:
        # PD above every configured upper bound (possible if the last max_pd < 1).
        return 0.0

    upper = thresholds[bucket_index].max_pd
    if bucket_index == 0:
        # Lowest (open-ended) bucket: single finite boundary at `upper`.
        nearest_half_width = (thresholds[1].max_pd - thresholds[0].max_pd) / 2.0
        return _clamp_unit((upper - pd) / nearest_half_width)

    lower = thresholds[bucket_index - 1].max_pd
    if bucket_index == len(thresholds) - 1:
        # Highest (open-ended) bucket: the configured final bound is the PD
        # ceiling, not a rating cut-off. Normalize the distance from the lower
        # cut-off by the nearest finite bucket's half-width (the B bucket for
        # the canonical table).
        if len(thresholds) >= 3:
            nearest_half_width = (
                thresholds[-2].max_pd - thresholds[-3].max_pd
            ) / 2.0
        else:
            nearest_half_width = (thresholds[-1].max_pd - lower) / 2.0
        return _clamp_unit((pd - lower) / nearest_half_width)

    half_width = (upper - lower) / 2.0
    margin = min(pd - lower, upper - pd)
    return _clamp_unit(margin / half_width)


def compute_tier1_confidence(
    bundle: EvidenceBundle,
    proxy: ConfidenceProxy,
    *,
    band_dispersion_ref: float,
    thresholds: Sequence[RatingThreshold],
) -> float:
    """Return the selected Tier 1 confidence proxy for a validated bundle.

    Args:
        bundle: Evidence bundle carrying Tier 1 `pd` and Tier 2 `pd_band`.
        proxy: Configured `tier3.tier1_confidence_proxy`.
        band_dispersion_ref: Positive normalizer for proxy A.
        thresholds: Ascending rating brackets for proxy B.

    Returns:
        Confidence in `[0, 1]`; `0.0` when the proxy's required input is absent.

    Raises:
        ValueError: If `proxy` is not a supported literal.
    """
    if proxy == PROXY_BAND_DISPERSION:
        if bundle.pd_band is None:
            return 0.0
        return band_dispersion_confidence(
            bundle.pd_band, reference_width=band_dispersion_ref
        )
    if proxy == PROXY_RATING_BOUNDARY_MARGIN:
        if bundle.pd is None:
            return 0.0
        return rating_boundary_margin_confidence(bundle.pd, thresholds)
    raise ValueError(f"Unsupported Tier 1 confidence proxy: {proxy!r}.")


def _validate_thresholds(thresholds: Sequence[RatingThreshold]) -> None:
    """Reject a malformed rating table instead of silently mis-bucketing PD."""
    if len(thresholds) < 2:
        raise ValueError("At least two rating thresholds are required.")
    for threshold in thresholds:
        if not math.isfinite(threshold.max_pd) or not 0.0 <= threshold.max_pd <= 1.0:
            raise ValueError(
                f"Rating threshold for {threshold.rating!r} must be finite and in "
                f"[0.0, 1.0]; got {threshold.max_pd!r}."
            )
    if thresholds[0].max_pd <= 0.0:
        raise ValueError("The first rating threshold must be > 0.0.")
    for previous, current in zip(thresholds, thresholds[1:], strict=False):
        if current.max_pd <= previous.max_pd:
            raise ValueError(
                "Rating thresholds must be strictly increasing; got "
                f"{previous.max_pd!r} then {current.max_pd!r}."
            )


def _clamp_unit(value: float) -> float:
    """Clamp a floating-point result to `[0, 1]` against arithmetic drift."""
    return min(1.0, max(0.0, value))
