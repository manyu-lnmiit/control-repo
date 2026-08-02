from context_compactor.models import Message
from context_compactor.summarizer import ExtractiveSummarizer, make_callable_summarizer


def test_empty_list_returns_empty_string():
    assert ExtractiveSummarizer().summarize([]) == ""


def test_summary_mentions_message_count():
    messages = [
        Message(role="user", content="First point. Second point. Third point."),
        Message(role="assistant", content="Reply one. Reply two."),
    ]
    summary = ExtractiveSummarizer().summarize(messages)
    assert "2 earlier messages" in summary


def test_summary_includes_role_tags():
    messages = [Message(role="user", content="Please fix the login bug.")]
    summary = ExtractiveSummarizer().summarize(messages)
    assert "[user]" in summary


def test_summary_respects_max_chars():
    long_text = "This is a sentence. " * 200
    messages = [Message(role="user", content=long_text)]
    summarizer = ExtractiveSummarizer(max_chars=100)
    summary = summarizer.summarize(messages)
    assert len(summary) <= 100


def test_max_sentences_per_message_limits_extraction():
    text = "Sentence one. Sentence two. Sentence three. Sentence four."
    messages = [Message(role="user", content=text)]
    summarizer = ExtractiveSummarizer(max_sentences_per_message=1)
    summary = summarizer.summarize(messages)
    assert "Sentence one." in summary
    assert "Sentence four." not in summary


def test_make_callable_summarizer_wraps_plain_function():
    def fn(messages):
        return f"custom summary of {len(messages)} messages"

    summarizer = make_callable_summarizer(fn)
    messages = [Message(role="user", content="hi"), Message(role="assistant", content="hello")]
    assert summarizer.summarize(messages) == "custom summary of 2 messages"
