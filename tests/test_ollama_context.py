"""Tests for parsing Ollama /api/show context metadata."""

from __future__ import annotations

from blender_gpt.ollama_client import (
    parse_model_info_context_length,
    parse_parameters_num_ctx,
    resolve_context_settings,
    suggest_max_scene_chars,
)

SAMPLE_SHOW = {
    "model": "llama3.2",
    "parameters": "num_ctx                        32768\n",
    "model_info": {
        "general.architecture": "llama",
        "llama.context_length": 131072,
    },
}


def test_parse_model_info_context_length():
    assert parse_model_info_context_length(SAMPLE_SHOW["model_info"]) == 131072


def test_parse_parameters_num_ctx_from_string():
    assert parse_parameters_num_ctx(SAMPLE_SHOW["parameters"]) == 32768


def test_resolve_context_uses_min_of_model_and_configured():
    out = resolve_context_settings(SAMPLE_SHOW)
    assert out["num_ctx"] == 32768
    assert out["max_scene_chars"] == suggest_max_scene_chars(32768)


def test_resolve_context_large_model():
    out = resolve_context_settings(
        {"model_info": {"llama.context_length": 262144}, "parameters": ""}
    )
    assert out["num_ctx"] == 262144
    assert out["max_scene_chars"] > 400_000


def test_resolve_context_unknown_defaults():
    out = resolve_context_settings({})
    assert out["num_ctx"] == 0
    assert out["max_scene_chars"] == 48_000
