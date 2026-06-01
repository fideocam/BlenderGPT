"""Tests for user message / digest wiring used for scene *description* in prompts."""

from __future__ import annotations

from blender_gpt.system_prompt import (
    SYSTEM_PROMPT,
    build_system_prompt,
    build_user_message,
    load_system_prompt_rules,
)


def test_build_user_message_includes_digest_and_request():
    digest = "Scene: Scene\n\nSelection:\n  (none)"
    prompt = "Describe the default setup."
    msg = build_user_message(digest, prompt)
    assert "=== Scene digest ===" in msg
    assert digest in msg
    assert "=== User request ===" in msg
    assert "Describe the default setup." in msg


def test_describe_request_preserved():
    """Ensure a describe-only question is passed through intact."""
    out = build_user_message("Scene: S", "What objects are visible?")
    assert "What objects are visible?" in out


def test_system_prompt_loads_rules_file():
    rules = load_system_prompt_rules()
    assert "Selection and reference words" in rules
    assert "active_object" in rules
    assert '{"actions":[]}' in rules


def test_system_prompt_includes_rules_and_schema():
    prompt = build_system_prompt()
    assert "BlenderGPT" in prompt
    assert "create_primitive" in prompt
    assert SYSTEM_PROMPT == prompt
