"""Tests for Ollama model name resolution."""

from __future__ import annotations

import blender_gpt.ollama_client as oc


def test_resolve_exact_and_short_name(monkeypatch):
    names = ["llama3.2:latest", "qwen2.5-coder:1.5b"]
    monkeypatch.setattr(oc, "list_model_names", lambda base_url, timeout=5.0: names)
    assert oc.resolve_model_name("http://x", "llama3.2:latest") == "llama3.2:latest"
    assert oc.resolve_model_name("http://x", "llama3.2") == "llama3.2:latest"
