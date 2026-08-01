from llm_gateway.models import ChatMessage, ChatRequest, Role, Usage


def test_chat_message_roundtrip():
    msg = ChatMessage(role=Role.USER, content="hi")
    d = msg.to_dict()
    assert d == {"role": "user", "content": "hi"}
    assert ChatMessage.from_dict(d) == msg


def test_chat_request_prompt_chars():
    req = ChatRequest(
        model="m",
        messages=[
            ChatMessage(role=Role.SYSTEM, content="abcd"),
            ChatMessage(role=Role.USER, content="ef"),
        ],
    )
    assert req.prompt_chars() == 6


def test_usage_total_tokens():
    u = Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.01)
    assert u.total_tokens == 15
