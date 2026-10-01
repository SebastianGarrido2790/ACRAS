"""Tier 1 ML Service Module.

Scope: FastAPI serving layer and thin inference wrapper around the frozen,
calibrated PD model artifact produced by `src/pipelines/training/`.

Architectural Invariant (INV-1 & ADR-010):
This module contains ONLY serving and inference code. It never executes or
re-implements training logic; it only loads and serves frozen, registered artifacts.
"""

from src.tier1_ml.app import app, create_app
from src.tier1_ml.rating import map_pd_to_credit_rating
from src.tier1_ml.schemas import InferenceRequest, InferenceResponse
from src.tier1_ml.service import DEFAULT_BUNDLE_PATH, Tier1ModelService

__all__ = [
    "DEFAULT_BUNDLE_PATH",
    "InferenceRequest",
    "InferenceResponse",
    "Tier1ModelService",
    "app",
    "create_app",
    "map_pd_to_credit_rating",
]

