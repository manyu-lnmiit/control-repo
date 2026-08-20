"""End-to-end tests for the parse pipeline and retry loop."""

from __future__ import annotations

import pytest

from outputcontract import (
    ContractViolation,
    ExtractionError,
    RetryBudgetExceeded,
    parse,
    parse_with_retries,
)

PERSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "email": {"type": "string"},
    },
    "required": ["name", "age"],
}


def test_parse_clean_output():
    result = parse('{"name": "Ada", "age": 36}', PERSON_SCHEMA)
    assert result.value == {"name": "Ada", "age": 36}
    assert result.was_clean


def test_parse_fenced_and_coerced():
    raw = 'Here you go:\n```json\n{"name": "Ada", "age": "36"}\n```'
    result = parse(raw, PERSON_SCHEMA)
    assert result.value == {"name": "Ada", "age": 36}
    assert result.source == "fence"
    assert result.coercions


def test_parse_repairs_and_validates():
    raw = "{name: 'Ada', age: 36,}"
    result = parse(raw, PERSON_SCHEMA)
    assert result.value == {"name": "Ada", "age": 36}
    assert result.repairs


def test_parse_missing_required_raises_contract_violation():
    with pytest.raises(ContractViolation) as excinfo:
        parse('{"name": "Ada"}', PERSON_SCHEMA)
    issues = excinfo.value.issues
    assert any(issue.validator == "required" for issue in issues)


def test_parse_no_payload_raises():
    with pytest.raises(ExtractionError):
        parse("no json here at all", PERSON_SCHEMA)


def test_parse_skips_bad_candidate_for_valid_one():
    raw = 'prose {oops not json here!} more prose {"name": "Ada", "age": 36}'
    result = parse(raw, PERSON_SCHEMA)
    assert result.value["name"] == "Ada"


def test_retry_succeeds_after_feedback():
    attempts = []

    def call_model(feedback):
        attempts.append(feedback)
        if feedback is None:
            return '{"name": "Ada"}'  # missing age
        return '{"name": "Ada", "age": 36}'

    result = parse_with_retries(call_model, PERSON_SCHEMA, max_attempts=3)
    assert result.value == {"name": "Ada", "age": 36}
    assert attempts[0] is None
    assert "age" in attempts[1]


def test_retry_budget_exceeded():
    def call_model(feedback):
        return '{"name": "Ada"}'  # always missing age

    with pytest.raises(RetryBudgetExceeded) as excinfo:
        parse_with_retries(call_model, PERSON_SCHEMA, max_attempts=2)
    assert excinfo.value.attempts == 2
    assert isinstance(excinfo.value.last_error, ContractViolation)


def test_on_attempt_observer_called():
    events = []

    def call_model(feedback):
        return '{"name": "Ada", "age": 36}'

    parse_with_retries(
        call_model,
        PERSON_SCHEMA,
        on_attempt=lambda i, raw, err: events.append((i, err)),
    )
    assert events == [(1, None)]


def test_retry_recovers_from_non_json():
    calls = {"n": 0}

    def call_model(feedback):
        calls["n"] += 1
        if calls["n"] == 1:
            return "I'm sorry, I cannot help with that."
        return '{"name": "Ada", "age": 36}'

    result = parse_with_retries(call_model, PERSON_SCHEMA, max_attempts=3)
    assert result.value["name"] == "Ada"
