"""Unit tests for PersonaVerdict parsing and bounded-repair validation (W-A4)."""

from __future__ import annotations

import pytest

from src.schemas import (
    PersonaVerdict,
    PersonaVerdictValidationError,
    parse_persona_verdict,
    with_bounded_repair,
)

VALID = (
    '{"persona": "cro", "recommendation": "reject", "lean": -1.0, '
    '"confidence": 0.9, "rationale": "Negative equity and sustained negative '
    'operating cash flow indicate elevated tail risk."}'
)


def test_parse_valid_verdict() -> None:
    verdict = parse_persona_verdict(VALID)
    assert isinstance(verdict, PersonaVerdict)
    assert verdict.persona == "cro"
    assert verdict.recommendation == "reject"
    assert verdict.lean == -1.0
    assert verdict.confidence == 0.9


def test_parse_accepts_code_fenced_json() -> None:
    verdict = parse_persona_verdict(f"```json\n{VALID}\n```")
    assert verdict.recommendation == "reject"


def test_parse_malformed_json_fails_loudly() -> None:
    with pytest.raises(PersonaVerdictValidationError):
        parse_persona_verdict('{"persona": "cro", ')


def test_parse_truncated_json_fails_loudly() -> None:
    with pytest.raises(PersonaVerdictValidationError):
        parse_persona_verdict(VALID[:30])


def test_parse_wrong_enum_fails_loudly() -> None:
    bad = VALID.replace('"reject"', '"decline"')
    with pytest.raises(PersonaVerdictValidationError):
        parse_persona_verdict(bad)


def test_parse_lean_out_of_bounds_fails() -> None:
    bad = VALID.replace("-1.0", "1.5")
    with pytest.raises(PersonaVerdictValidationError):
        parse_persona_verdict(bad)


def test_parse_short_rationale_fails() -> None:
    bad = VALID.replace(
        "Negative equity and sustained negative operating cash flow indicate "
        "elevated tail risk.",
        "short",
    )
    with pytest.raises(PersonaVerdictValidationError):
        parse_persona_verdict(bad)


def test_bounded_repair_recovers_on_second_attempt() -> None:
    attempts = {"n": 0}

    def call() -> str:
        attempts["n"] += 1
        return VALID if attempts["n"] == 2 else "{bad json"

    result = with_bounded_repair(call, parse_persona_verdict, max_repairs=1)
    assert isinstance(result, PersonaVerdict)
    assert attempts["n"] == 2


def test_bounded_repair_gives_up_after_one_repair() -> None:
    attempts = {"n": 0}

    def call() -> str:
        attempts["n"] += 1
        return "{always bad"

    with pytest.raises(PersonaVerdictValidationError):
        with_bounded_repair(call, parse_persona_verdict, max_repairs=1)
    assert attempts["n"] == 2  # one initial call + exactly one repair
