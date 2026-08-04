import pytest

from injection_radar.models import Finding, RiskLevel, ScanResult


def test_finding_rejects_invalid_span():
    with pytest.raises(ValueError):
        Finding(detector="d", category="c", message="m", span=(5, 2), matched_text="x", severity=10)


def test_finding_rejects_invalid_severity():
    with pytest.raises(ValueError):
        Finding(detector="d", category="c", message="m", span=(0, 1), matched_text="x", severity=150)


def test_scan_result_no_findings_is_clean():
    result = ScanResult(text="hello world")
    assert result.score == 0.0
    assert result.risk_level == RiskLevel.NONE
    assert result.is_suspicious is False


def test_scan_result_score_combines_diminishing_returns():
    f1 = Finding(detector="d", category="c1", message="m", span=(0, 1), matched_text="a", severity=50)
    f2 = Finding(detector="d", category="c2", message="m", span=(1, 2), matched_text="b", severity=50)
    result = ScanResult(text="ab", findings=[f1, f2])
    # 1 - (0.5 * 0.5) = 0.75 -> 75.0, strictly less than a naive sum of 100.
    assert result.score == 75.0
    assert result.score < 100.0


def test_scan_result_score_never_exceeds_100():
    findings = [
        Finding(detector="d", category="c", message="m", span=(i, i + 1), matched_text="x", severity=90)
        for i in range(5)
    ]
    result = ScanResult(text="x" * 5, findings=findings)
    assert result.score <= 100.0


def test_risk_level_from_score_boundaries():
    assert RiskLevel.from_score(0) == RiskLevel.NONE
    assert RiskLevel.from_score(10) == RiskLevel.LOW
    assert RiskLevel.from_score(30) == RiskLevel.MEDIUM
    assert RiskLevel.from_score(55) == RiskLevel.HIGH
    assert RiskLevel.from_score(80) == RiskLevel.CRITICAL
    assert RiskLevel.from_score(100) == RiskLevel.CRITICAL


def test_top_findings_sorted_by_severity():
    f1 = Finding(detector="d", category="c1", message="m", span=(0, 1), matched_text="a", severity=10)
    f2 = Finding(detector="d", category="c2", message="m", span=(1, 2), matched_text="b", severity=90)
    result = ScanResult(text="ab", findings=[f1, f2])
    top = result.top_findings(n=1)
    assert top == [f2]


def test_to_dict_roundtrip_shape():
    f1 = Finding(detector="d", category="c1", message="m", span=(0, 1), matched_text="a", severity=10)
    result = ScanResult(text="ab", findings=[f1])
    d = result.to_dict()
    assert d["risk_level"] == result.risk_level.name
    assert d["findings"][0]["category"] == "c1"
