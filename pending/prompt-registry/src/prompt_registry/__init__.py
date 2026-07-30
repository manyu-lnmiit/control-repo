"""prompt-registry: git-like version control, diffing, and safe rollout for LLM prompt templates."""

from prompt_registry.ab import ExperimentConfig, Variant, choose_variant
from prompt_registry.models import PromptVersion, RenderResult
from prompt_registry.store import PromptNotFoundError, PromptRegistry, VersionNotFoundError
from prompt_registry.template import MissingVariableError, extract_variables, render_template

__all__ = [
    "PromptVersion",
    "RenderResult",
    "PromptRegistry",
    "PromptNotFoundError",
    "VersionNotFoundError",
    "render_template",
    "extract_variables",
    "MissingVariableError",
    "ExperimentConfig",
    "Variant",
    "choose_variant",
]

__version__ = "0.1.0"
