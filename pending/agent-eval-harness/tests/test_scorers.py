import pytest

from agent_eval_harness.scorers import (
    Composite,
    Contains,
    ExactMatch,
    NumericTolerance,
    RegexMatch,
    ScoreResult,
    build_scorer,
    register_scorer,
)


def test_exact_match_pass():
    r = ExactMatch().score("hello", "hello")
    assert r.passed and r.score == 1.0


def test_exact_match_case_insensitive():
    r = ExactMatch(case_sensitive=False).score("Hello", "hello")
    assert r.passed


def test_exact_match_fail():
    r = ExactMatch().score("hello", "world")
    assert not r.passed and r.score == 0.0


def test_contains_single_needle():
    assert Contains().score("the sky is blue", "blue").passed


def test_contains_list_any():
    r = Contains(require_all=False).score("red apple", ["red", "green"])
    assert r.passed


def test_contains_list_require_all():
    r = Contains(require_all=True).score("red and green", ["red", "green"])
    assert r.passed
    r2 = Contains(require_all=True).score("red only", ["red", "green"])
    assert not r2.passed
    assert r2.score == 0.5


def test_regex_match():
    r = RegexMatch().score("order-2024-01-01", r"\d{4}-\d{2}-\d{2}")
    assert r.passed


def test_regex_no_match():
    r = RegexMatch().score("no dates here", r"\d{4}-\d{2}-\d{2}")
    assert not r.passed


@pytest.mark.parametrize(
    "output,expected,abs_tol,passed",
    [
        (42, 42, 1e-6, True),
        ("42", "42", 1e-6, True),
        ("$1,200.50", 1200.5, 0.01, True),
        (41.9, 42, 0.05, False),
        (41.9, 42, 0.2, True),
    ],
)
def test_numeric_tolerance(output, expected, abs_tol, passed):
    r = NumericTolerance(abs_tol=abs_tol).score(output, expected)
    assert r.passed is passed


def test_numeric_tolerance_relative():
    r = NumericTolerance(abs_tol=0, rel_tol=0.1).score(105, 100)
    assert r.passed
    r2 = NumericTolerance(abs_tol=0, rel_tol=0.01).score(105, 100)
    assert not r2.passed


def test_numeric_tolerance_unparseable():
    r = NumericTolerance().score("not a number", 42)
    assert not r.passed and r.score == 0.0


def test_composite_averages_and_thresholds():
    scorer = Composite(
        [(ExactMatch(), 1.0), (Contains(), 1.0)],
        pass_threshold=0.5,
    )
    # ExactMatch fails (0.0), Contains passes (1.0) -> average 0.5 -> passes at threshold 0.5
    r = scorer.score("has blue in it", "blue")
    assert r.passed
    assert r.score == 0.5


def test_composite_requires_at_least_one_scorer():
    with pytest.raises(ValueError):
        Composite([])


def test_score_result_validates_range():
    with pytest.raises(ValueError):
        ScoreResult(score=1.5, passed=True)


def test_build_scorer_registry():
    scorer = build_scorer("exact_match", case_sensitive=False)
    assert isinstance(scorer, ExactMatch)


def test_build_scorer_unknown_raises():
    with pytest.raises(KeyError):
        build_scorer("does_not_exist")


def test_register_custom_scorer():
    class AlwaysPass:
        def score(self, output, expected):
            return ScoreResult(score=1.0, passed=True, detail="always")

    register_scorer("always_pass", AlwaysPass)
    scorer = build_scorer("always_pass")
    assert scorer.score("x", "y").passed
