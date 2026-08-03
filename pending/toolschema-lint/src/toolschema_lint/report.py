"""Output formatters for a :class:`~toolschema_lint.linter.LintResult`.

Three formats are supported:

* ``text`` -- human-readable, colorless, for terminals and CI logs.
* ``json`` -- machine-readable, for downstream tooling.
* ``sarif`` -- SARIF 2.1.0, so results can be uploaded as GitHub code
  scanning annotations (``github/codeql-action/upload-sarif``).
"""

from __future__ import annotations

import json as _json

from toolschema_lint.linter import LintResult

_SARIF_SEVERITY_MAP = {
    "error": "error",
    "warning": "warning",
    "info": "note",
}


def format_text(result: LintResult) -> str:
    lines = []
    for finding in result.sorted_findings():
        lines.append(finding.format())
    lines.append("")
    lines.append(
        f"Checked {result.tool_count} tool(s): "
        f"{result.error_count} error(s), {result.warning_count} warning(s), "
        f"{result.info_count} info."
    )
    return "\n".join(lines)


def format_json(result: LintResult) -> str:
    payload = {
        "tool_count": result.tool_count,
        "summary": {
            "errors": result.error_count,
            "warnings": result.warning_count,
            "info": result.info_count,
        },
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "message": f.message,
                "tool_name": f.tool_name,
                "parameter_name": f.parameter_name,
            }
            for f in result.sorted_findings()
        ],
    }
    return _json.dumps(payload, indent=2)


def format_sarif(result: LintResult) -> str:
    rule_ids = sorted({f.rule_id for f in result.findings})
    rules = [{"id": rid, "shortDescription": {"text": rid.replace("-", " ")}} for rid in rule_ids]

    sarif_results = []
    for f in result.sorted_findings():
        location_name = f.tool_name if not f.parameter_name else f"{f.tool_name}.{f.parameter_name}"
        sarif_results.append(
            {
                "ruleId": f.rule_id,
                "level": _SARIF_SEVERITY_MAP[f.severity.value],
                "message": {"text": f.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "tool-schema"},
                        },
                        "logicalLocations": [{"name": location_name}],
                    }
                ],
            }
        )

    payload = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "toolschema-lint",
                        "informationUri": "https://github.com/manyu-lnmiit/toolschema-lint",
                        "rules": rules,
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return _json.dumps(payload, indent=2)


FORMATTERS = {
    "text": format_text,
    "json": format_json,
    "sarif": format_sarif,
}
