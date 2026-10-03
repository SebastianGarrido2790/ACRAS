"""Container Integration Tests for Tier 1 ML Service (Stage 7).

Governed by:
    ADR-010: Pure serving container decoupled from training pipelines.
    ADR-022: Lean joblib bundle serving with zero MLflow runtime dependency.

Falsification & Gate 7 Checks:
    1. Verify MLflow is verifiably absent from the container (attempting import raises
       ModuleNotFoundError).
    2. Verify live HTTP requests against the containerized FastAPI service score correctly.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd
import pytest

from src.schemas.features import CANONICAL_FEATURES

IMAGE_TAG = "acras-tier1:stage7"
CONTAINER_NAME = "acras-tier1-integration-test"
CONTAINER_PORT = 8008


@pytest.fixture(scope="module")
def docker_ready() -> str:
    """Ensure docker is available, daemon is running, and test image is built."""
    if not shutil.which("docker"):
        pytest.skip("Docker CLI not available on system.")

    res = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if res.returncode != 0:
        pytest.skip("Docker daemon is not running.")

    res_img = subprocess.run(
        ["docker", "image", "inspect", IMAGE_TAG],
        capture_output=True,
        text=True,
    )
    if res_img.returncode != 0:
        pytest.skip(
            f"Docker image '{IMAGE_TAG}' not found locally. "
            f"Build it with 'docker build -t {IMAGE_TAG} .' first."
        )

    return IMAGE_TAG


def test_container_falsification_zero_mlflow(docker_ready: str) -> None:
    """Falsification: Attempting to import mlflow inside container MUST fail loudly.

    Proves that MLflow is verifiably absent from the runtime container (ADR-022).
    """
    res = subprocess.run(
        ["docker", "run", "--rm", docker_ready, "python", "-c", "import mlflow"],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "ModuleNotFoundError" in res.stderr
    assert "mlflow" in res.stderr


def test_container_falsification_training_deps_absent(docker_ready: str) -> None:
    """Falsification: Training-only deps (DVC, Great Expectations) must be absent."""
    res_dvc = subprocess.run(
        ["docker", "run", "--rm", docker_ready, "python", "-c", "import dvc"],
        capture_output=True,
        text=True,
    )
    assert res_dvc.returncode != 0
    assert "ModuleNotFoundError" in res_dvc.stderr

    res_gx = subprocess.run(
        ["docker", "run", "--rm", docker_ready, "python", "-c", "import great_expectations"],
        capture_output=True,
        text=True,
    )
    assert res_gx.returncode != 0
    assert "ModuleNotFoundError" in res_gx.stderr


def test_live_container_service_scoring(docker_ready: str) -> None:
    """Gate 7: Live requests against containerized service return valid PD and rating."""
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

    run_proc = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            "-p",
            f"{CONTAINER_PORT}:8000",
            docker_ready,
        ],
        capture_output=True,
        text=True,
    )
    assert run_proc.returncode == 0, f"Failed to start container: {run_proc.stderr}"

    try:
        base_url = f"http://localhost:{CONTAINER_PORT}"
        ready = False
        degraded = False
        for _ in range(20):
            try:
                with urllib.request.urlopen(f"{base_url}/health", timeout=2) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except urllib.error.HTTPError as err:
                if err.code == 503:
                    degraded = True
                    break
            except Exception:
                time.sleep(0.5)

        if degraded:
            pytest.skip(
                "Containerized service responded with HTTP 503 "
                "(promoted bundle absent at build time)."
            )

        assert ready, "Containerized service failed to reach healthy status within 10s."

        raw_path = Path("data/raw/data.csv")
        if not raw_path.is_file():
            pytest.skip("data/raw/data.csv not present.")

        df = pd.read_csv(raw_path, nrows=1)
        features = {col: float(df[col].iloc[0]) for col in CANONICAL_FEATURES}

        payload = {
            "company_id": "CONTAINER-INTEG-001",
            "raw_features": features,
        }
        post_req = urllib.request.Request(
            f"{base_url}/predict",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(post_req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["company_id"] == "CONTAINER-INTEG-001"
            assert 0.0 <= data["pd"] <= 1.0
            assert isinstance(data["credit_rating"], str)
            assert data["model_family"] == "xgboost"

        bad_features = dict(features)
        del bad_features[CANONICAL_FEATURES[0]]
        bad_req = urllib.request.Request(
            f"{base_url}/predict",
            data=json.dumps({"company_id": "PROBE", "raw_features": bad_features}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(bad_req, timeout=5)
        assert exc_info.value.code == 422

    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
