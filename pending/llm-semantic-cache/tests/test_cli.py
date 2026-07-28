from click.testing import CliRunner

from semantic_cache.cache import SemanticCache
from semantic_cache.cli import main


def test_stats_command(tmp_path):
    db_path = str(tmp_path / "cache.db")
    cache = SemanticCache(path=db_path)
    cache.set("hello world", "hi there", cost_estimate=0.03)
    cache.get("hello world")
    cache.close()

    runner = CliRunner()
    result = runner.invoke(main, ["stats", "--path", db_path])
    assert result.exit_code == 0
    assert "entries:" in result.output
    assert "total_hits:" in result.output


def test_lookup_command_hit_and_miss(tmp_path):
    db_path = str(tmp_path / "cache.db")
    cache = SemanticCache(path=db_path, threshold=0.7)
    cache.set("what is the capital of france", "Paris")
    cache.close()

    runner = CliRunner()
    hit_result = runner.invoke(
        main, ["lookup", "--path", db_path, "--threshold", "0.7", "what's the capital of france"]
    )
    assert hit_result.exit_code == 0
    assert "HIT" in hit_result.output

    miss_result = runner.invoke(
        main, ["lookup", "--path", db_path, "write me a sonnet about databases"]
    )
    assert miss_result.exit_code == 0
    assert "MISS" in miss_result.output


def test_purge_command(tmp_path):
    db_path = str(tmp_path / "cache.db")
    runner = CliRunner()
    result = runner.invoke(main, ["purge", "--path", db_path])
    assert result.exit_code == 0
    assert "purged" in result.output


def test_clear_command_with_confirmation(tmp_path):
    db_path = str(tmp_path / "cache.db")
    cache = SemanticCache(path=db_path)
    cache.set("hello", "world")
    cache.close()

    runner = CliRunner()
    result = runner.invoke(main, ["clear", "--path", db_path], input="y\n")
    assert result.exit_code == 0
    assert "removed" in result.output
