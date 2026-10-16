"""Gateway configuration schemas, secret resolution, and cost accounting.

Governed by:
    D3-01: Shared httpx transport and configuration boundary.
    D3-03: Resilience parameters (timeouts, breaker thresholds, zero retries).
    D3-04: Versioned cost accounting; unknown cost remains unknown.
    GW-FR-02 / GW-FR-03 / GW-FR-09 / GW-FR-10: Strict bounds, no credentials
        in YAML, safe out-of-band secret resolution.
"""

from __future__ import annotations

import os
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.gateway.contracts import (
    GatewayError,
    GatewayErrorCategory,
    ProviderUsage,
)


class CostRateConfig(BaseModel):
    """Pricing rates in USD per 1,000,000 tokens for a specific model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_per_m: Annotated[float, Field(ge=0.0, description="Cost per 1M input tokens in USD.")]
    output_per_m: Annotated[float, Field(ge=0.0, description="Cost per 1M output tokens in USD.")]
    rate_date: Annotated[str, Field(min_length=1, description="Date of verified pricing rate.")]
    rate_source: Annotated[str, Field(min_length=1, description="Source or reference URL of rate.")]


class ProviderSettings(BaseModel):
    """Execution parameters for an individual provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Annotated[
        str, Field(min_length=1, description="Provider name (e.g. 'gemini', 'groq').")
    ]
    model: Annotated[str, Field(min_length=1, description="Exact pinned model identifier.")]
    base_url: Annotated[str, Field(min_length=1, description="Base API URL endpoint.")]
    timeout_s: Annotated[
        float,
        Field(gt=0.0, le=120.0, description="Per-request timeout in seconds for this provider."),
    ]


class GatewayConfig(BaseModel):
    """Root configuration contract for Phase 3 LLM Gateway."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary: ProviderSettings
    fallback: ProviderSettings
    max_attempts: Annotated[int, Field(ge=1, le=5, default=2)] = 2
    retries_per_provider: Annotated[int, Field(ge=0, le=3, default=0)] = 0
    breaker_failure_threshold: Annotated[int, Field(ge=1, le=20, default=3)] = 3
    breaker_recovery_timeout_s: Annotated[float, Field(ge=1.0, le=300.0, default=30.0)] = 30.0
    breaker_half_open_probes: Annotated[int, Field(ge=1, le=5, default=1)] = 1
    cost_rates: dict[str, CostRateConfig] = Field(default_factory=dict)
    default_user_agent: Annotated[
        str,
        Field(
            min_length=1,
            default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ACRAS/1.0",
            description="Browser-style User-Agent header (required for Cloudflare clearance).",
        ),
    ] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ACRAS/1.0"


def resolve_api_key(provider: str) -> str:
    """Resolve an API key out-of-band from environment variables.

    Never reads from or exposes keys into version-controlled configuration.

    Args:
        provider: Provider identifier (e.g. 'gemini', 'groq', 'huggingface').

    Returns:
        The non-empty API key string.

    Raises:
        GatewayError: If the required environment variable is absent or empty.
    """
    key_name: str
    prov_norm = provider.strip().lower()

    if prov_norm == "gemini":
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        key_name = "GEMINI_API_KEY"
    elif prov_norm == "groq":
        key = os.environ.get("GROQ_API_KEY")
        key_name = "GROQ_API_KEY"
    elif prov_norm in ("huggingface", "hf"):
        key = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
        key_name = "HF_TOKEN"
    else:
        key_name = f"{prov_norm.upper()}_API_KEY"
        key = os.environ.get(key_name)

    if not key or not key.strip():
        raise GatewayError(
            category=GatewayErrorCategory.CONFIG_OR_AUTH_ERROR,
            message=(
                f"Missing API credential for provider '{provider}'. "
                f"Ensure environment variable '{key_name}' is set."
            ),
            provider=provider,
        )

    return key.strip()


def calculate_cost_usd(
    model: str,
    usage: ProviderUsage | None,
    cost_rates: dict[str, CostRateConfig],
) -> float | None:
    """Calculate request cost in USD from usage and versioned rate configurations.

    Per GW-FR-09 and D3-04: Unknown usage or unknown rates MUST return None,
    never assumed as 0.0.

    Args:
        model: Exact model identifier.
        usage: Provider-reported usage object.
        cost_rates: Mapping of model identifier to CostRateConfig.

    Returns:
        Cost in USD rounded to 8 decimal places, or None if unknown.
    """
    if usage is None:
        return None

    rate = cost_rates.get(model)
    if rate is None:
        return None

    cost = (
        usage.prompt_tokens * rate.input_per_m
        + usage.completion_tokens * rate.output_per_m
    ) / 1_000_000.0

    return round(float(cost), 8)
