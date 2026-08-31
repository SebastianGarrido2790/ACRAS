"""Training Pipeline Module.

Scope: FTI Training stage responsible for feature ingestion, model training,
calibration verification (Brier score / reliability curve), and model artifact registration.

Architectural Invariant (INV-7 & ADR-010):
This module produces the frozen model artifact registered for serving.
Training code and serving code (`src/tier1_ml/`) are strictly separated.
All training runs must be gated by Great Expectations data contracts.
"""
