import json

import pytest

from toolschema_lint.config import Config
from toolschema_lint.models import Severity


def test_default_config_has_no_disabled_rules():
    config = Config()
    assert config.disabled_rules == set()
    assert config.similarity_threshold == 0.6


def test_from_dict_parses_disable_and_severity():
    config = Config.from_dict(
        {
            "disable": ["vague-tool-name"],
            "severity": {"missing-tool-description": "warning"},
            "similarity_threshold": 0.8,
        }
    )
    assert "vague-tool-name" in config.disabled_rules
    assert config.severity_overrides["missing-tool-description"] == Severity.WARNING
    assert config.similarity_threshold == 0.8


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Config.load(tmp_path / "nope.json")


def test_load_reads_json_file(tmp_path):
    path = tmp_path / ".toolschemalintrc.json"
    path.write_text(json.dumps({"disable": ["x"]}))
    config = Config.load(path)
    assert config.disabled_rules == {"x"}


def test_find_and_load_returns_default_when_absent(tmp_path):
    config = Config.find_and_load(tmp_path)
    assert config.disabled_rules == set()


def test_find_and_load_discovers_config(tmp_path):
    (tmp_path / ".toolschemalintrc.json").write_text(json.dumps({"disable": ["y"]}))
    config = Config.find_and_load(tmp_path)
    assert config.disabled_rules == {"y"}
