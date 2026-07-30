import pytest

from prompt_registry.store import (
    PromptNotFoundError,
    PromptRegistry,
    VersionNotFoundError,
)
from prompt_registry.template import MissingVariableError


@pytest.fixture
def registry():
    reg = PromptRegistry(":memory:")
    yield reg
    reg.close()


def test_commit_starts_at_version_one(registry):
    pv = registry.commit("greeting", "Hello, {{name}}!", message="initial")
    assert pv.version == 1
    assert pv.parent_version is None


def test_commit_increments_version(registry):
    registry.commit("greeting", "v1 body", message="initial")
    pv2 = registry.commit("greeting", "v2 body", message="update")
    assert pv2.version == 2
    assert pv2.parent_version == 1


def test_get_latest_returns_most_recent(registry):
    registry.commit("greeting", "v1", message="a")
    registry.commit("greeting", "v2", message="b")
    latest = registry.get("greeting")
    assert latest.body == "v2"
    assert latest.version == 2


def test_get_unknown_prompt_raises(registry):
    with pytest.raises(PromptNotFoundError):
        registry.get("does-not-exist")


def test_get_unknown_version_raises(registry):
    registry.commit("greeting", "v1", message="a")
    with pytest.raises(VersionNotFoundError):
        registry.get("greeting", version=99)


def test_history_returns_all_versions_oldest_first(registry):
    registry.commit("greeting", "v1", message="a")
    registry.commit("greeting", "v2", message="b")
    registry.commit("greeting", "v3", message="c")
    history = registry.history("greeting")
    assert [pv.version for pv in history] == [1, 2, 3]


def test_diff_reports_line_changes(registry):
    registry.commit("greeting", "Hello, {{name}}!", message="a")
    registry.commit("greeting", "Hi there, {{name}}!", message="b")
    diff_text = registry.diff("greeting", 1, 2)
    assert "-Hello, {{name}}!" in diff_text
    assert "+Hi there, {{name}}!" in diff_text


def test_tag_moves_between_versions(registry):
    registry.commit("greeting", "v1", message="a")
    registry.commit("greeting", "v2", message="b")
    registry.tag("greeting", 1, "prod")
    tagged = registry.tag("greeting", 2, "prod")
    assert "prod" in tagged.tags
    v1 = registry.get("greeting", 1)
    assert "prod" not in v1.tags


def test_get_by_tag(registry):
    registry.commit("greeting", "v1", message="a")
    registry.commit("greeting", "v2", message="b")
    registry.tag("greeting", 1, "prod")
    pv = registry.get_by_tag("greeting", "prod")
    assert pv.version == 1


def test_get_by_tag_missing_raises(registry):
    registry.commit("greeting", "v1", message="a")
    with pytest.raises(VersionNotFoundError):
        registry.get_by_tag("greeting", "prod")


def test_rollback_creates_new_version_with_old_body(registry):
    registry.commit("greeting", "v1 body", message="a")
    registry.commit("greeting", "v2 body", message="b")
    rolled_back = registry.rollback("greeting", 1)
    assert rolled_back.version == 3
    assert rolled_back.body == "v1 body"
    # history is never mutated
    assert registry.get("greeting", 1).body == "v1 body"
    assert registry.get("greeting", 2).body == "v2 body"


def test_list_names(registry):
    registry.commit("a", "body-a", message="a")
    registry.commit("b", "body-b", message="b")
    assert registry.list_names() == ["a", "b"]


def test_render_by_latest_version(registry):
    registry.commit("greeting", "Hello, {{name}}!", message="a")
    result = registry.render("greeting", {"name": "Ada"})
    assert result.text == "Hello, Ada!"
    assert result.version == 1
    assert result.variables_used == ["name"]


def test_render_by_specific_version(registry):
    registry.commit("greeting", "Hi {{name}}", message="a")
    registry.commit("greeting", "Hey {{name}}", message="b")
    result = registry.render("greeting", {"name": "Ada"}, version=1)
    assert result.text == "Hi Ada"


def test_render_by_tag(registry):
    registry.commit("greeting", "Hi {{name}}", message="a")
    registry.commit("greeting", "Hey {{name}}", message="b")
    registry.tag("greeting", 1, "prod")
    result = registry.render("greeting", {"name": "Ada"}, tag="prod")
    assert result.text == "Hi Ada"
    assert result.version == 1


def test_render_missing_variable_raises(registry):
    registry.commit("greeting", "Hi {{name}}", message="a")
    with pytest.raises(MissingVariableError):
        registry.render("greeting", {})


def test_render_rejects_both_version_and_tag(registry):
    registry.commit("greeting", "Hi {{name}}", message="a")
    with pytest.raises(ValueError):
        registry.render("greeting", {"name": "Ada"}, version=1, tag="prod")


def test_metadata_round_trips(registry):
    pv = registry.commit(
        "greeting", "Hi {{name}}", message="a", metadata={"model": "gpt-4o", "temperature": 0.2}
    )
    fetched = registry.get("greeting", pv.version)
    assert fetched.metadata == {"model": "gpt-4o", "temperature": 0.2}
