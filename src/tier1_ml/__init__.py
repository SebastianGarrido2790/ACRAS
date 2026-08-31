"""Tier 1 ML Service Module.

Scope: FastAPI serving layer and thin inference wrapper around the frozen,
calibrated PD model artifact produced by `src/pipelines/training/`.

Architectural Invariant (INV-1 & ADR-010):
This module contains ONLY serving and inference code. It never executes or
re-implements training logic; it only loads and serves frozen, registered artifacts.
"""
