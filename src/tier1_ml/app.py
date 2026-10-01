"""FastAPI Application for Tier 1 ML PD Serving.

Governed by:
    INV-1 (ADR-001): Deterministic core served via FastAPI microservice.
    ADR-010: Serving code strictly decoupled from training pipelines.
    ADR-022: Loads lean joblib bundle at startup with zero MLflow dependency.
    D-1.8 (ADR-023): Validated against canonical feature list.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from src.tier1_ml.schemas import InferenceRequest, InferenceResponse
from src.tier1_ml.service import DEFAULT_BUNDLE_PATH, Tier1ModelService


def create_app(bundle_path: str = DEFAULT_BUNDLE_PATH) -> FastAPI:
    """Create and configure the Tier 1 FastAPI application.

    Args:
        bundle_path: Path to promoted model joblib bundle.

    Returns:
        Configured FastAPI application instance.
    """
    model_service: Tier1ModelService | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        nonlocal model_service
        try:
            model_service = Tier1ModelService(bundle_path=bundle_path)
            app.state.service = model_service
        except Exception as exc:
            # Service can still boot in uninitialized mode if artifact is missing in dev
            app.state.service = None
            app.state.init_error = str(exc)
        yield
        app.state.service = None

    app = FastAPI(
        title="ACRAS Tier 1 ML Service",
        description="Deterministic Calibrated Probability of Default (PD) scoring service.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["Monitoring"])
    async def health_check() -> JSONResponse:
        """Health and readiness check endpoint."""
        service = getattr(app.state, "service", None)
        if service is None:
            try:
                service = Tier1ModelService(bundle_path=bundle_path)
                app.state.service = service
            except Exception as exc:
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"status": "degraded", "error": str(exc)},
                )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "healthy",
                "model_family": service.model_family,
                "calibration_method": service.calibration_method,
                "brier_score": service.brier_score,
                "roc_auc": service.roc_auc,
            },
        )

    @app.post(
        "/predict",
        response_model=InferenceResponse,
        status_code=status.HTTP_200_OK,
        tags=["Inference"],
    )
    async def predict_endpoint(request: InferenceRequest) -> InferenceResponse:
        """Predict calibrated probability of default and rating bracket for a company."""
        service: Tier1ModelService | None = getattr(app.state, "service", None)
        if service is None:
            try:
                service = Tier1ModelService(bundle_path=bundle_path)
                app.state.service = service
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Tier 1 Model Service is unavailable: {exc}",
                ) from exc

        try:
            response = service.predict(request)
            return response
        except ValueError as val_err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(val_err),
            ) from val_err
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Inference execution failed: {exc}",
            ) from exc

    return app


# Default app instance for ASGI servers (uvicorn src.tier1_ml.app:app)
app = create_app()
