import json

import pytest

from agent_memory_store.cli import main


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_memory.db")


def test_add_and_list(db_path, capsys):
    rc = main(
        ["--db", db_path, "add", "remember the api key rotation policy", "--importance", "0.6"]
    )
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert len(out) == 32  # uuid4().hex length

    rc = main(["--db", db_path, "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "api key rotation policy" in out


def test_search_returns_results(db_path, capsys):
    main(["--db", db_path, "add", "the user's timezone is UTC+5:30"])
    main(["--db", db_path, "add", "the user likes espresso in the morning"])
    capsys.readouterr()

    rc = main(["--db", db_path, "search", "what timezone does the user use", "-k", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "timezone" in out.lower()
    assert "espresso" in out.lower()


def test_forget_missing_id_returns_nonzero(db_path, capsys):
    rc = main(["--db", db_path, "forget", "nonexistent-id"])
    assert rc == 1
    assert "not found" in capsys.readouterr().out


def test_stats_outputs_valid_json(db_path, capsys):
    main(["--db", db_path, "add", "a memory"])
    capsys.readouterr()
    rc = main(["--db", db_path, "stats"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == 1


def test_decay_command_runs(db_path, capsys):
    main(["--db", db_path, "add", "a decaying memory"])
    capsys.readouterr()
    rc = main(["--db", db_path, "decay"])
    assert rc == 0
    assert "updated" in capsys.readouterr().out


def test_consolidate_command_runs(db_path, capsys):
    for text in [
        "user reports slow load times on dashboard",
        "user again complains dashboard is slow",
        "user says dashboard loading is sluggish",
    ]:
        main(["--db", db_path, "add", text])
    capsys.readouterr()

    rc = main(
        ["--db", db_path, "consolidate", "--similarity-threshold", "0.3", "--min-cluster-size", "3"]
    )
    assert rc == 0
    assert "created" in capsys.readouterr().out
