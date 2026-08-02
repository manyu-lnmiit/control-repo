import json

from context_compactor.cli import build_parser, main


def _write_transcript(path, n=40):
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(
                json.dumps(
                    {
                        "role": "user" if i % 2 == 0 else "assistant",
                        "content": f"message number {i} with some extra padding text here",
                        "index": i,
                    }
                )
                + "\n"
            )


def test_parser_requires_command():
    parser = build_parser()
    try:
        parser.parse_args([])
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_compact_command_writes_output_file(tmp_path, capsys):
    transcript = tmp_path / "transcript.jsonl"
    output = tmp_path / "out.jsonl"
    _write_transcript(transcript)

    rc = main(["compact", str(transcript), "--max-tokens", "150", "--output", str(output)])
    assert rc == 0
    assert output.exists()

    lines = output.read_text().strip().splitlines()
    assert len(lines) >= 1
    for line in lines:
        data = json.loads(line)
        assert "role" in data and "content" in data

    captured = capsys.readouterr()
    assert "input:" in captured.err


def test_compact_command_no_summarize_flag(tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    output = tmp_path / "out.jsonl"
    _write_transcript(transcript)

    rc = main(
        [
            "compact",
            str(transcript),
            "--max-tokens",
            "150",
            "--output",
            str(output),
            "--no-summarize",
        ]
    )
    assert rc == 0
    lines = output.read_text().strip().splitlines()
    for line in lines:
        data = json.loads(line)
        assert "summary of" not in data["content"]


def test_stats_command_prints_token_totals(tmp_path, capsys):
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, n=5)

    rc = main(["stats", str(transcript)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "messages: 5" in out
    assert "total tokens" in out


def test_compact_command_stdout_when_no_output(tmp_path, capsys):
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, n=5)

    rc = main(["compact", str(transcript), "--max-tokens", "10000"])
    assert rc == 0
    out = capsys.readouterr().out
    lines = [line for line in out.strip().splitlines() if line]
    assert len(lines) == 5
