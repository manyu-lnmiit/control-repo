from agent_guardrail.redact import redact_pii, redact_text


def test_redact_email():
    assert redact_text("contact me at jane.doe@example.com") == "contact me at [REDACTED:EMAIL]"


def test_redact_ssn():
    assert redact_text("ssn: 123-45-6789") == "ssn: [REDACTED:SSN]"


def test_redact_phone():
    result = redact_text("call 415-555-1234 now")
    assert "[REDACTED:PHONE]" in result


def test_redact_ipv4():
    assert redact_text("server at 192.168.1.1") == "server at [REDACTED:IPV4]"


def test_redact_pii_nested_structures():
    value = {
        "user": {"email": "a@b.com", "notes": ["ip 10.0.0.1", "clean text"]},
        "count": 5,
    }
    redacted = redact_pii(value)
    assert redacted["user"]["email"] == "[REDACTED:EMAIL]"
    assert "[REDACTED:IPV4]" in redacted["user"]["notes"][0]
    assert redacted["user"]["notes"][1] == "clean text"
    assert redacted["count"] == 5


def test_redact_pii_passthrough_non_string():
    assert redact_pii(42) == 42
    assert redact_pii(None) is None
    assert redact_pii(3.14) == 3.14
