"""PersonaVerdict parsing and bounded-repair validation for Tier 3 structured output.

Governed by:
    INV-4 (ADR-004): Divergence is scored deterministically over the structured
        ``PersonaVerdict`` fields; invalid verdicts must never enter that function.
    R-05 / D-06 (remediation plan): A schema-invalid verdict triggers at most one
        bounded repair re-ask, then fails loudly as an incomplete result.
    INV-1 (ADR-001): Parsing here validates LLM output; it feeds no Tier 1/2
        deterministic calculation.
"""

from __future__ import annotations

from collections.abc import Callable

from src.schemas.evidence_bundle import PersonaVerdict


class PersonaVerdictValidationError(ValueError):
    """Raised when model output cannot be parsed into a valid ``PersonaVerdict``."""


def parse_persona_verdict(content: str) -> PersonaVerdict:
    """Parse and validate raw model text into a ``PersonaVerdict`` (fails loudly).

    Accepts a fenced code block (```json ... ```) as a convenience; anything that
    does not validate against the canonical schema raises.

    Args:
        content: Raw completion text from a provider.

    Returns:
        A validated ``PersonaVerdict``.

    Raises:
        PersonaVerdictValidationError: If the content is malformed, truncated, or
            does not match the schema (e.g. wrong enum value, out-of-range field).
    """
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return PersonaVerdict.model_validate_json(text)
    except Exception as exc:  # noqa: BLE001 - normalize any parse/validation failure
        raise PersonaVerdictValidationError(
            f"Invalid PersonaVerdict payload: {exc}"
        ) from exc


def with_bounded_repair[T](
    call: Callable[[], str],
    parse: Callable[[str], T],
    *,
    max_repairs: int = 1,
) -> T:
    """Run ``call`` once, then re-ask at most ``max_repairs`` times on parse failure.

    Args:
        call: Produces raw provider text for one attempt (the re-ask is the
            caller's responsibility via the same callable).
        parse: Validates raw text into ``T``, raising ``PersonaVerdictValidationError``
            on failure.
        max_repairs: Maximum number of repair re-asks beyond the initial call.

    Returns:
        The first successfully parsed value.

    Raises:
        PersonaVerdictValidationError: If parsing fails after ``max_repairs`` repairs.
    """
    attempts = 0
    while True:
        raw = call()
        try:
            return parse(raw)
        except PersonaVerdictValidationError:
            if attempts >= max_repairs:
                raise
            attempts += 1
