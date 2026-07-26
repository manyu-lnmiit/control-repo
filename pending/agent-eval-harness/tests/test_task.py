import json

import pytest
import yaml
from pydantic import ValidationError

from agent_eval_harness.task import Task, TaskSuite, load_suite


def test_task_requires_nonblank_id():
    with pytest.raises(ValidationError):
        Task(id="  ", prompt="hi")


def test_task_weight_must_be_positive():
    with pytest.raises(ValidationError):
        Task(id="t1", prompt="hi", weight=0)


def test_suite_rejects_duplicate_ids():
    with pytest.raises(ValidationError):
        TaskSuite(
            name="s",
            tasks=[
                Task(id="dup", prompt="a"),
                Task(id="dup", prompt="b"),
            ],
        )


def test_filter_by_tag():
    suite = TaskSuite(
        name="s",
        tasks=[
            Task(id="a", prompt="p", tags=["math"]),
            Task(id="b", prompt="p", tags=["reasoning"]),
        ],
    )
    filtered = suite.filter_by_tag("math")
    assert len(filtered) == 1
    assert filtered.tasks[0].id == "a"


def test_load_suite_yaml(tmp_path):
    data = {
        "name": "yaml-suite",
        "tasks": [{"id": "t1", "prompt": "hi", "scorer": "exact_match", "expected": "hi"}],
    }
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.safe_dump(data))
    suite = load_suite(p)
    assert suite.name == "yaml-suite"
    assert len(suite) == 1


def test_load_suite_json(tmp_path):
    data = {
        "name": "json-suite",
        "tasks": [{"id": "t1", "prompt": "hi"}],
    }
    p = tmp_path / "suite.json"
    p.write_text(json.dumps(data))
    suite = load_suite(p)
    assert suite.name == "json-suite"


def test_load_suite_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_suite(tmp_path / "nope.yaml")


def test_load_suite_bad_extension(tmp_path):
    p = tmp_path / "suite.txt"
    p.write_text("not really a suite")
    with pytest.raises(ValueError):
        load_suite(p)


def test_load_suite_non_mapping_top_level(tmp_path):
    p = tmp_path / "suite.json"
    p.write_text(json.dumps([1, 2, 3]))
    with pytest.raises(TypeError):
        load_suite(p)
