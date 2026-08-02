"""The core compaction engine.

`Compactor.compact()` takes a full message transcript and a `TokenBudget`
and returns a `CompactionResult` whose messages fit the budget while
preserving as much of the original meaning and order as possible:

1. Pinned messages are always kept verbatim.
2. Remaining messages are scored by an `ImportanceScorer`.
3. The highest-scoring messages are kept verbatim, greedily, until the
   budget (minus what pinned messages already cost) is spent.
4. Contiguous runs of *dropped* messages are collapsed into a single
   summary message via a `Summarizer`, inserted at the run's original
   position, so conversational order is preserved.
5. If summarizing still doesn't fit (pathological tiny budgets), the
   lowest-value summary blocks are evicted entirely as a last resort.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from context_compactor.models import CompactionResult, CompactionStats, Message
from context_compactor.scoring import DefaultImportanceScorer, ImportanceScorer
from context_compactor.summarizer import ExtractiveSummarizer, Summarizer
from context_compactor.tokenizer import Tokenizer, get_default_tokenizer


class EvictionStrategy(str, Enum):
    """How to handle messages that don't make the cut."""

    SUMMARIZE = "summarize"  # collapse dropped runs into a summary message
    DROP = "drop"  # discard dropped messages entirely, no summary


@dataclass
class TokenBudget:
    """Describes how much context space is available.

    Attributes:
        max_tokens: total token budget for the returned message list.
        reserve_tokens: tokens to hold back for the model's response
            (subtracted from max_tokens to get the usable budget).
        min_summary_tokens: a summary block is only worth inserting if it
            saves at least this many tokens versus keeping the messages
            verbatim; otherwise the run is just dropped.
    """

    max_tokens: int
    reserve_tokens: int = 0
    min_summary_tokens: int = 8

    @property
    def usable_tokens(self) -> int:
        return max(0, self.max_tokens - self.reserve_tokens)


class Compactor:
    """Fits a message transcript into a token budget."""

    def __init__(
        self,
        tokenizer: Tokenizer | None = None,
        scorer: ImportanceScorer | None = None,
        summarizer: Summarizer | None = None,
        strategy: EvictionStrategy = EvictionStrategy.SUMMARIZE,
    ) -> None:
        self.tokenizer = tokenizer or get_default_tokenizer()
        self.scorer = scorer or DefaultImportanceScorer()
        self.summarizer = summarizer or ExtractiveSummarizer()
        self.strategy = strategy

    def _token_count(self, message: Message) -> int:
        if message.token_count is None:
            message.token_count = self.tokenizer.count(message.content)
        return message.token_count

    def compact(self, messages: list[Message], budget: TokenBudget) -> CompactionResult:
        if not messages:
            stats = CompactionStats(0, 0, 0, 0, 0, 0, 0)
            return CompactionResult(messages=[], stats=stats)

        input_tokens = sum(self._token_count(m) for m in messages)
        usable = budget.usable_tokens

        if input_tokens <= usable:
            stats = CompactionStats(
                input_messages=len(messages),
                output_messages=len(messages),
                input_tokens=input_tokens,
                output_tokens=input_tokens,
                dropped_messages=0,
                summarized_messages=0,
                summary_blocks_created=0,
            )
            return CompactionResult(messages=list(messages), stats=stats)

        ordered = sorted(messages, key=lambda m: m.index)
        total = len(ordered)

        pinned = [m for m in ordered if m.pinned]
        pinned_tokens = sum(self._token_count(m) for m in pinned)
        remaining_budget = max(0, usable - pinned_tokens)

        candidates = [m for m in ordered if not m.pinned]
        scored = [
            (self.scorer.score(m, position=i, total=total), m)
            for i, m in enumerate(ordered)
            if not m.pinned
        ]
        # Highest score first; stable tie-break on original index keeps
        # earlier messages slightly favored over later ones of equal score.
        scored.sort(key=lambda pair: (-pair[0], pair[1].index))

        keep_ids: set[int] = set()
        spent = 0
        for _score, m in scored:
            cost = self._token_count(m)
            if spent + cost <= remaining_budget:
                keep_ids.add(id(m))
                spent += cost

        dropped = [m for m in candidates if id(m) not in keep_ids]

        # Build the output preserving original order: walk through `ordered`,
        # emitting pinned/kept messages verbatim and collapsing contiguous
        # runs of dropped messages into a single summary block.
        output: list[Message] = []
        run: list[Message] = []
        summary_blocks_created = 0
        summarized_count = 0
        dropped_ids = {id(m) for m in dropped}

        def flush_run() -> None:
            nonlocal run, summary_blocks_created, summarized_count
            if not run:
                return
            if self.strategy == EvictionStrategy.SUMMARIZE:
                verbatim_cost = sum(self._token_count(m) for m in run)
                summary_text = self.summarizer.summarize(run)
                summary_msg = Message(
                    role="system",
                    content=summary_text,
                    index=run[0].index,
                    metadata={"kind": "compaction_summary", "source_count": len(run)},
                )
                summary_cost = self.tokenizer.count(summary_text)
                if verbatim_cost - summary_cost >= budget.min_summary_tokens:
                    output.append(summary_msg)
                    summary_blocks_created += 1
                    summarized_count += len(run)
                # else: not worth it, the run is simply dropped (no block emitted)
            run = []

        for m in ordered:
            if id(m) in dropped_ids:
                run.append(m)
                continue
            flush_run()
            output.append(m)
        flush_run()

        output.sort(key=lambda m: m.index)

        # Last-resort trim: if we're still over budget (e.g. many small
        # summary blocks, or a tiny budget), evict summary blocks with the
        # lowest information density (shortest content) until it fits.
        def total_tokens(msgs: list[Message]) -> int:
            return sum(self._token_count(m) for m in msgs)

        output_tokens = total_tokens(output)
        if output_tokens > usable:
            summary_indices = [
                i for i, m in enumerate(output) if m.metadata.get("kind") == "compaction_summary"
            ]
            summary_indices.sort(key=lambda i: self._token_count(output[i]))
            evict: set[int] = set()
            running_total = output_tokens
            for i in summary_indices:
                if running_total <= usable:
                    break
                running_total -= self._token_count(output[i])
                evict.add(i)
            output = [m for i, m in enumerate(output) if i not in evict]
            output_tokens = total_tokens(output)

        dropped_final = total - len(output)
        stats = CompactionStats(
            input_messages=total,
            output_messages=len(output),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            dropped_messages=max(0, dropped_final),
            summarized_messages=summarized_count,
            summary_blocks_created=summary_blocks_created,
        )
        return CompactionResult(messages=output, stats=stats)
