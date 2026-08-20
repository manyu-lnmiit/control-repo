"""Runnable example: parse messy model output into a typed contract.

Run with::

    python examples/basic_usage.py
"""

from __future__ import annotations

import dataclasses

from outputcontract import parse, parse_with_retries, schema_from


@dataclasses.dataclass
class Ticket:
    title: str
    priority: str  # one of low / medium / high
    story_points: int
    blocked: bool


TICKET_SCHEMA = schema_from(Ticket)
TICKET_SCHEMA["properties"]["priority"]["enum"] = ["low", "medium", "high"]


def demo_single_parse() -> None:
    # A realistic, messy model response: prose + fence + wrong types + smart quotes.
    raw = """Sure, here's the ticket you asked for:

```json
{
    title: 'Fix flaky auth test',   // model dropped the quotes on the key
    "priority": "HIGH",             // wrong case for the enum
    "story_points": "3",            // a string where we want an int
    "blocked": "yes",               // a yes/no where we want a bool
}
```

Let me know if you'd like anything changed!"""

    result = parse(raw, TICKET_SCHEMA)
    print("parsed value :", result.value)
    print("repairs      :", result.repairs)
    print("coercions    :", result.coercions)
    print("was clean    :", result.was_clean)


def demo_retry_loop() -> None:
    # Simulate a model that forgets a field on the first attempt, then fixes it
    # after being handed structured feedback.
    attempts = iter(
        [
            '{"title": "Add rate limiting", "priority": "medium", "blocked": false}',
            '{"title": "Add rate limiting", "priority": "medium", '
            '"story_points": 5, "blocked": false}',
        ]
    )

    def call_model(feedback: str | None) -> str:
        if feedback:
            print("\n-- feedback sent back to the model --")
            print(feedback)
        return next(attempts)

    result = parse_with_retries(call_model, TICKET_SCHEMA, max_attempts=3)
    print("\nfinal value  :", result.value)


if __name__ == "__main__":
    print("=== single parse ===")
    demo_single_parse()
    print("\n=== retry loop ===")
    demo_retry_loop()
