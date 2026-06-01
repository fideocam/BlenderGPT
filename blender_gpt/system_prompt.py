"""Load system prompt from editable text files under blender_gpt/prompts/."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_RULES_FILE = "system_prompt_rules.txt"
_SCHEMA_FILE = "action_schema.txt"


def _read_prompt_file(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"BlenderGPT prompt file missing: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_system_prompt_rules() -> str:
    """Natural-language interaction rules (selection, units, explain vs change)."""
    return _read_prompt_file(_RULES_FILE)


def load_action_schema() -> str:
    """Allowlisted JSON ops reference sent to the model."""
    return _read_prompt_file(_SCHEMA_FILE)


def build_system_prompt() -> str:
    rules = load_system_prompt_rules()
    schema = load_action_schema()
    return f"{rules}\n\n\n=== Action schema ===\n\n{schema}"


# Built once at import; reload addon in Blender after editing prompt files.
SYSTEM_PROMPT = build_system_prompt()


def build_user_message(scene_digest: str, user_prompt: str) -> str:
    return (
        "=== Scene digest ===\n"
        + scene_digest.strip()
        + "\n\n=== User request ===\n"
        + user_prompt.strip()
    )
