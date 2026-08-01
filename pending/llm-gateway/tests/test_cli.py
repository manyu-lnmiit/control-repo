import json

from llm_gateway.cli import build_parser, main


def test_chat_command_prints_openai_shaped_json(capsys):
    exit_code = main(["chat", "hello there", "--model", "mock-small"])
    assert exit_code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"]["content"]


def test_validate_command_on_valid_default_config(tmp_path, capsys):
    from llm_gateway.config import DEFAULT_CONFIG_YAML

    config_file = tmp_path / "config.yaml"
    config_file.write_text(DEFAULT_CONFIG_YAML)

    exit_code = main(["validate", str(config_file)])
    assert exit_code == 0
    assert "valid" in capsys.readouterr().out


def test_validate_command_on_invalid_config(tmp_path, capsys):
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("providers: []\n")

    exit_code = main(["validate", str(config_file)])
    assert exit_code == 1
    assert "invalid config" in capsys.readouterr().err


def test_parser_requires_subcommand():
    parser = build_parser()
    assert parser.prog == "llm-gateway"
