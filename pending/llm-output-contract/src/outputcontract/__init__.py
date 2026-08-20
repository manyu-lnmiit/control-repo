"""outputcontract — turn messy LLM text into schema-valid structured data.

The public surface is intentionally small::

    from outputcontract import parse, parse_with_retries, schema_from

``parse`` runs the full extract → repair → coerce → validate pipeline on a
single model response. ``parse_with_retries`` drives a repair loop that feeds
schema feedback back to the model. ``schema_from`` derives a JSON Schema from a
Python type so you only declare the contract once.
"""

from __future__ import annotations

from outputcontract.coerce import CoercionResult, coerce_to_schema
from outputcontract.errors import (
    ContractViolation,
    ExtractionError,
    OutputContractError,
    RepairError,
    RetryBudgetExceeded,
)
from outputcontract.extract import Candidate, extract, find_candidates
from outputcontract.pipeline import (
    ParseResult,
    parse,
    parse_with_retries,
    render_feedback,
)
from outputcontract.repair import RepairResult, repair_json
from outputcontract.schema_gen import schema_from
from outputcontract.validate import SchemaValidator, ValidationIssue

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "parse",
    "parse_with_retries",
    "render_feedback",
    "ParseResult",
    "extract",
    "find_candidates",
    "Candidate",
    "repair_json",
    "RepairResult",
    "coerce_to_schema",
    "CoercionResult",
    "SchemaValidator",
    "ValidationIssue",
    "schema_from",
    "OutputContractError",
    "ExtractionError",
    "RepairError",
    "ContractViolation",
    "RetryBudgetExceeded",
]
