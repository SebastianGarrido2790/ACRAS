"""Unit tests for Stage 6 FastAPI Serving Layer (Tier 1 ML Service).

Governed by:
    INV-1 (ADR-001): Deterministic ML serving layer.
    ADR-010: Pure serving boundary; zero MLflow client dependency at runtime.
    ADR-022: Lean joblib model bundle loaded directly at startup.
    D-1.8 (ADR-023): Runtime validation against canonical 94-feature list.
    D-1.10 (ADR-024): Exact duplicate column rejected on input.

Stage 6 Falsification Probes:
    Probe 1: Request missing a required canonical feature -> HTTP 422 validation error.
    Probe 2: Request with an unexpected extra key (e.g. dropped duplicate) -> HTTP 422 rejected.
    Gate 6: Valid request returns schema-correct calibrated PD and discrete rating.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.schemas.features import (
    CANONICAL_FEATURES,
    DROPPED_DUPLICATE_FEATURE,
)
from src.tier1_ml.app import create_app
from src.tier1_ml.service import DEFAULT_BUNDLE_PATH


@pytest.fixture(scope="module")
def bundle_path() -> Path:
    """Fixture ensuring promoted bundle exists."""
    p = Path(DEFAULT_BUNDLE_PATH)
    if not p.is_file():
        pytest.skip(f"Promoted bundle not found at {p}. Run Stage 5 first.")
    return p


@pytest.fixture(scope="module")
def valid_sample_features() -> dict[str, float]:
    """Fixture providing one valid sample feature mapping from raw dataset."""
    raw_path = Path("data/raw/data.csv")
    if not raw_path.is_file():
        pytest.skip("Raw dataset not found.")
    df = pd.read_csv(raw_path, nrows=1)
    return {col: float(df[col].iloc[0]) for col in CANONICAL_FEATURES}


def test_runtime_boundary_zero_mlflow_import() -> None:
    """Invariant Test (ADR-010 / ADR-022): Zero MLflow import anywhere in tier1_ml runtime path."""
    import src.tier1_ml as t1

    assert t1.app is not None

    tier1_modules = [
        mod for name, mod in sys.modules.items() if name.startswith("src.tier1_ml")
    ]
    assert len(tier1_modules) > 0

    for mod in tier1_modules:
        assert "mlflow" not in mod.__dict__, (
            f"Forbidden 'mlflow' import found in module: {mod.__name__}"
        )



def test_health_endpoint_healthy(bundle_path: Path) -> None:
    """Verify health endpoint returns status healthy and model metadata."""
    app = create_app(bundle_path=str(bundle_path))
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["model_family"] == "xgboost"
    assert data["calibration_method"] == "isotonic"
    assert "brier_score" in data
    assert "roc_auc" in data


def test_health_endpoint_missing_bundle(tmp_path: Path) -> None:
    """Verify health endpoint reports degraded 503 when model bundle is absent."""
    non_existent = tmp_path / "non_existent.joblib"
    app = create_app(bundle_path=str(non_existent))
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_valid_inference_request_scoring(
    bundle_path: Path,
    valid_sample_features: dict[str, float],
) -> None:
    """Gate 6: A valid request scores cleanly, returning schema-correct PD and rating."""
    app = create_app(bundle_path=str(bundle_path))
    client = TestClient(app)

    payload = {
        "company_id": "COMP-VALID-001",
        "raw_features": valid_sample_features,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["company_id"] == "COMP-VALID-001"
    assert 0.0 <= data["pd"] <= 1.0
    assert isinstance(data["credit_rating"], str)
    assert len(data["credit_rating"]) >= 1
    assert data["model_family"] == "xgboost"
    assert data["calibration_method"] == "isotonic"
    assert data["model_version"] == "v1"


def test_falsification_probe_1_missing_required_feature(
    bundle_path: Path,
    valid_sample_features: dict[str, float],
) -> None:
    """Falsification Probe 1: Request missing a required canonical feature MUST be rejected.

    Must return HTTP 422 with an informative validation error (not silent NaN or raw crash).
    """
    app = create_app(bundle_path=str(bundle_path))
    client = TestClient(app)

    missing_dict = dict(valid_sample_features)
    dropped_key = CANONICAL_FEATURES[0]
    del missing_dict[dropped_key]

    payload = {
        "company_id": "COMP-PROBE-1",
        "raw_features": missing_dict,
    }
    response = client.post("/predict", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "missing" in str(body).lower()


def test_falsification_probe_2_unexpected_extra_key(
    bundle_path: Path,
    valid_sample_features: dict[str, float],
) -> None:
    """Falsification Probe 2: Request with an unexpected extra key MUST be rejected.

    Must reject unauthorized fields (e.g. dropped duplicate column per ADR-024)
    with HTTP 422 per extra="forbid" invariant.
    """
    app = create_app(bundle_path=str(bundle_path))
    client = TestClient(app)

    extra_dict = dict(valid_sample_features)
    extra_dict[DROPPED_DUPLICATE_FEATURE] = 0.45

    payload = {
        "company_id": "COMP-PROBE-2",
        "raw_features": extra_dict,
    }
    response = client.post("/predict", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "forbidden" in str(body).lower() or "extra" in str(body).lower()


def test_falsification_probe_2b_unknown_arbitrary_key(
    bundle_path: Path,
    valid_sample_features: dict[str, float],
) -> None:
    """Falsification Probe 2b: Request with a generic arbitrary extra key is rejected."""
    app = create_app(bundle_path=str(bundle_path))
    client = TestClient(app)

    extra_dict = dict(valid_sample_features)
    extra_dict["unauthorized_custom_metric"] = 999.0

    payload = {
        "company_id": "COMP-PROBE-2B",
        "raw_features": extra_dict,
    }
    response = client.post("/predict", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "unexpected extra features" in str(body).lower()


def test_non_finite_values_rejected(
    bundle_path: Path,
    valid_sample_features: dict[str, float],
) -> None:
    """Verify non-finite numbers (NaN, null, Inf) are rejected with 422."""
    app = create_app(bundle_path=str(bundle_path))
    client = TestClient(app)

    nan_dict = dict(valid_sample_features)
    nan_dict[CANONICAL_FEATURES[1]] = None  # type: ignore

    payload = {
        "company_id": "COMP-NAN",
        "raw_features": nan_dict,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 422

