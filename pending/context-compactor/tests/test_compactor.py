from context_compactor.compactor import Compactor, EvictionStrategy, TokenBudget
from context_compactor.models import Message


def make_messages(n: int, role: str = "user", prefix: str = "message") -> list[Message]:
    return [
        Message(role=role, content=f"{prefix} number {i} with some extra padding text here")
        for i in range(n)
    ]


def test_no_compaction_needed_when_under_budget():
    messages = make_messages(3)
    compactor = Compactor()
    result = compactor.compact(messages, TokenBudget(max_tokens=10_000))
    assert len(result.messages) == 3
    assert result.stats.dropped_messages == 0
    assert result.stats.summary_blocks_created == 0
    assert result.messages == messages


def test_empty_input_returns_empty_result():
    compactor = Compactor()
    result = compactor.compact([], TokenBudget(max_tokens=100))
    assert result.messages == []
    assert result.stats.input_messages == 0


def test_output_fits_within_budget():
    messages = make_messages(50)
    compactor = Compactor()
    budget = TokenBudget(max_tokens=200)
    result = compactor.compact(messages, budget)
    assert result.stats.output_tokens <= budget.usable_tokens


def test_pinned_messages_always_survive():
    messages = make_messages(50)
    messages[0].pinned = True
    messages[0].content = "SYSTEM PROMPT: always keep this one, it is pinned."
    compactor = Compactor()
    result = compactor.compact(messages, TokenBudget(max_tokens=150))
    assert any(m.content == messages[0].content for m in result.messages)


def test_reserve_tokens_shrinks_usable_budget():
    budget = TokenBudget(max_tokens=1000, reserve_tokens=400)
    assert budget.usable_tokens == 600


def test_drop_strategy_never_emits_summary_blocks():
    messages = make_messages(50)
    compactor = Compactor(strategy=EvictionStrategy.DROP)
    result = compactor.compact(messages, TokenBudget(max_tokens=150))
    assert result.stats.summary_blocks_created == 0
    for m in result.messages:
        assert m.metadata.get("kind") != "compaction_summary"


def test_summarize_strategy_creates_summary_blocks_for_large_transcripts():
    messages = make_messages(100)
    compactor = Compactor(strategy=EvictionStrategy.SUMMARIZE)
    result = compactor.compact(messages, TokenBudget(max_tokens=200))
    assert result.stats.summary_blocks_created >= 1


def test_output_preserves_relative_order():
    messages = make_messages(30)
    compactor = Compactor()
    result = compactor.compact(messages, TokenBudget(max_tokens=200))
    indices = [m.index for m in result.messages]
    assert indices == sorted(indices)


def test_high_importance_message_survives_over_low_importance_ones():
    messages = make_messages(40)
    # Bury one critically important message in the middle of low-value chatter.
    messages[20] = Message(
        role="user",
        content="short",
        importance=1.0,
        index=messages[20].index,
    )
    compactor = Compactor()
    result = compactor.compact(messages, TokenBudget(max_tokens=150))
    assert any(m.content == "short" for m in result.messages)


def test_tiny_budget_does_not_crash_and_stays_within_bound():
    messages = make_messages(20)
    compactor = Compactor()
    budget = TokenBudget(max_tokens=5)
    result = compactor.compact(messages, budget)
    assert result.stats.output_tokens <= budget.usable_tokens or len(result.messages) == 0


def test_custom_tokenizer_is_used_for_counting():
    class FixedTokenizer:
        def count(self, text: str) -> int:
            return 1  # every message costs exactly 1 token

    messages = make_messages(10)
    compactor = Compactor(tokenizer=FixedTokenizer())
    result = compactor.compact(messages, TokenBudget(max_tokens=10_000))
    assert result.stats.input_tokens == 10


def test_as_chat_messages_returns_plain_dicts():
    messages = make_messages(2)
    compactor = Compactor()
    result = compactor.compact(messages, TokenBudget(max_tokens=10_000))
    chat = result.as_chat_messages()
    assert chat == [{"role": m.role, "content": m.content} for m in messages]


def test_compression_ratio_and_tokens_saved_are_consistent():
    messages = make_messages(80)
    compactor = Compactor()
    result = compactor.compact(messages, TokenBudget(max_tokens=200))
    stats = result.stats
    assert stats.tokens_saved == max(0, stats.input_tokens - stats.output_tokens)
    if stats.input_tokens > 0:
        assert 0 <= stats.compression_ratio <= 1.01
