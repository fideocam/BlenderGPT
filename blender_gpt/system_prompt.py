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


def build_print_mode_user_message(scene_digest: str, user_prompt: str) -> str:
    """Print-prep request wrapper used by the Prepare for Print button."""
    return (
        "=== Scene digest ===\n"
        + scene_digest.strip()
        + "\n\n=== User request ===\n"
        + user_prompt.strip()
        + "\n\n=== Print mode (strict) ===\n"
        + "This request is for 3D printing. Prioritize printability and machine-safe geometry.\n"
        + "Use this workflow unless user explicitly asks otherwise:\n"
        + "1) set_print_units\n"
        + "2) create/modify geometry to match dimensions\n"
        + "3) add printability fixes (minimum wall/feature sizes, clearances)\n"
        + "4) merge_by_distance and normals_make_consistent\n"
        + "5) origin_to_geometry and place_on_build_plate\n"
        + "6) apply_scale\n"
        + "7) export_stl only if filepath is provided\n"
        + "If details are missing, choose practical defaults and state assumptions briefly."
    )
