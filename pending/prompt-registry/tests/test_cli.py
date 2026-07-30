import json

import pytest

from prompt_registry.cli import main


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


def test_commit_and_show(db_path, capsys):
    rc = main(["--db", db_path, "commit", "greeting", "--body", "Hi {{name}}", "-m", "init"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "committed greeting@v1" in out

    rc = main(["--db", db_path, "show", "greeting"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["version"] == 1
    assert data["body"] == "Hi {{name}}"


def test_log_lists_history(db_path, capsys):
    main(["--db", db_path, "commit", "greeting", "--body", "v1", "-m", "first"])
    main(["--db", db_path, "commit", "greeting", "--body", "v2", "-m", "second"])
    capsys.readouterr()
    rc = main(["--db", db_path, "log", "greeting"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "v1" in out and "v2" in out
    assert "first" in out and "second" in out


def test_list_names(db_path, capsys):
    main(["--db", db_path, "commit", "a", "--body", "body-a", "-m", "m"])
    main(["--db", db_path, "commit", "b", "--body", "body-b", "-m", "m"])
    capsys.readouterr()
    rc = main(["--db", db_path, "list"])
    assert rc == 0
    out = capsys.readouterr().out.split()
    assert out == ["a", "b"]


def test_diff_command(db_path, capsys):
    main(["--db", db_path, "commit", "greeting", "--body", "Hello", "-m", "m"])
    main(["--db", db_path, "commit", "greeting", "--body", "Hi", "-m", "m"])
    capsys.readouterr()
    rc = main(["--db", db_path, "diff", "greeting", "1", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "-Hello" in out
    assert "+Hi" in out


def test_rollback_command(db_path, capsys):
    main(["--db", db_path, "commit", "greeting", "--body", "v1", "-m", "m"])
    main(["--db", db_path, "commit", "greeting", "--body", "v2", "-m", "m"])
    capsys.readouterr()
    rc = main(["--db", db_path, "rollback", "greeting", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "new v3" in out


def test_tag_command(db_path, capsys):
    main(["--db", db_path, "commit", "greeting", "--body", "v1", "-m", "m"])
    capsys.readouterr()
    rc = main(["--db", db_path, "tag", "greeting", "1", "prod"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tagged greeting@v1 as 'prod'" in out


def test_render_command_with_vars(db_path, capsys):
    main(["--db", db_path, "commit", "greeting", "--body", "Hello, {{name}}!", "-m", "m"])
    capsys.readouterr()
    rc = main(["--db", db_path, "render", "greeting", "--var", "name=Ada"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip() == "Hello, Ada!"


def test_render_missing_variable_returns_error_exit_code(db_path, capsys):
    main(["--db", db_path, "commit", "greeting", "--body", "Hello, {{name}}!", "-m", "m"])
    capsys.readouterr()
    rc = main(["--db", db_path, "render", "greeting"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "error" in err


def test_show_unknown_prompt_returns_error_exit_code(db_path):
    rc = main(["--db", db_path, "show", "does-not-exist"])
    assert rc == 1
