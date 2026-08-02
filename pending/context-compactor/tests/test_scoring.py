from context_compactor.models import Message
from context_compactor.scoring import DefaultImportanceScorer


def test_manual_importance_override_wins():
    scorer = DefaultImportanceScorer()
    m = Message(role="user", content="whatever", importance=0.42)
    assert scorer.score(m, position=0, total=10) == 0.42


def test_recency_increases_score():
    scorer = DefaultImportanceScorer()
    old = Message(role="user", content="this is a normal length message about stuff")
    new = Message(role="user", content="this is a normal length message about stuff")
    old_score = scorer.score(old, position=0, total=10)
    new_score = scorer.score(new, position=9, total=10)
    assert new_score > old_score


def test_system_role_scores_higher_than_tool_role_at_same_position():
    scorer = DefaultImportanceScorer()
    system_msg = Message(role="system", content="a message of decent length here")
    tool_msg = Message(role="tool", content="a message of decent length here")
    assert scorer.score(system_msg, position=5, total=10) > scorer.score(
        tool_msg, position=5, total=10
    )


def test_keyword_signal_boosts_score():
    scorer = DefaultImportanceScorer()
    plain = Message(role="assistant", content="Sure, here is a normal response to your request.")
    signal = Message(
        role="assistant", content="Critical error: the deployment failed and must be fixed."
    )
    assert scorer.score(signal, position=5, total=10) > scorer.score(plain, position=5, total=10)


def test_very_short_message_penalized():
    scorer = DefaultImportanceScorer()
    short = Message(role="user", content="ok")
    longer = Message(role="user", content="ok, that sounds like a reasonable plan to me")
    # Compare at the same position; short messages get a multiplicative penalty.
    short_score = scorer.score(short, position=5, total=10)
    longer_score = scorer.score(longer, position=5, total=10)
    assert short_score < longer_score
