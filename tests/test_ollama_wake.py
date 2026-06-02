"""Tests for Ollama wake / connection helpers."""

from __future__ import annotations

from blender_gpt import ollama_client


def test_wait_for_connection_succeeds_when_check_passes(monkeypatch):
    calls = {"n": 0}

    def fake_check(base_url, timeout=3.0):
        calls["n"] += 1
        return calls["n"] >= 2

    monkeypatch.setattr(ollama_client, "check_connection", fake_check)
    monkeypatch.setattr(ollama_client, "_try_launch_ollama_host", lambda: True)
    monkeypatch.setattr(ollama_client.time, "sleep", lambda _: None)

    assert ollama_client.wait_for_connection("http://127.0.0.1:11434", attempts=3) is True
    assert calls["n"] == 2


def test_warm_model_uses_cache(monkeypatch):
    ollama_client._warm_cache.clear()
    posts: list[str] = []

    def fake_post(base_url, path, payload, timeout):
        posts.append(path)
        return {}

    monkeypatch.setattr(ollama_client, "_post_json", fake_post)
    ollama_client.warm_model("http://127.0.0.1:11434", "test-model")
    ollama_client.warm_model("http://127.0.0.1:11434", "test-model")
    assert posts == ["/api/generate"]
