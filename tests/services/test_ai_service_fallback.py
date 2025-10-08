"""Unit tests covering AI service fallback behaviour."""

from types import SimpleNamespace

import importlib


def _reload_ai(monkeypatch, allow_fallback="1"):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_STUB", "0")
    monkeypatch.setenv("AI_ALLOW_FALLBACK", allow_fallback)
    monkeypatch.setenv("AI_FALLBACK_LANGUAGE", "de")
    import health_app.services.ai_service as ai
    return importlib.reload(ai)


def test_call_chat_returns_localised_fallback(monkeypatch):
    ai = _reload_ai(monkeypatch)

    # Ensure non-stub + allow fallback
    monkeypatch.setattr(ai, "_STUB", False)
    monkeypatch.setattr(ai, "_ALLOW_FALLBACK", True)

    def _raise(*_, **__):
        raise RuntimeError("boom")

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_raise))
    )
    monkeypatch.setattr(ai, "_NEW_SDK", True)
    monkeypatch.setattr(ai, "_client", fake_client)

    result_de = ai._call_chat(
        [{"role": "user", "content": "hello"}],
        max_retries=0,
        language="de",
    )
    assert any(result_de.startswith(prefix) for prefix in ai.FALLBACK_PREFIXES), result_de
    assert "vorübergehende Dienstunterbrechung" in result_de
    assert "Diese Hinweise ersetzen keine ärztliche Beratung." in result_de

    result_en = ai._call_chat(
        [{"role": "user", "content": "hello"}],
        max_retries=0,
        language="en",
    )
    assert any(result_en.startswith(prefix) for prefix in ai.FALLBACK_PREFIXES), result_en
    assert "temporary service interruption" in result_en
    assert "MedAssistant fallback response:" in result_en


def test_chat_json_falls_back_to_stub_on_parse_error(monkeypatch):
    ai = _reload_ai(monkeypatch)

    monkeypatch.setattr(ai, "_STUB", False)
    monkeypatch.setattr(ai, "_ALLOW_FALLBACK", True)
    monkeypatch.setattr(ai, "_call_chat", lambda *a, **k: "not json")

    payload = ai.chat_json("prompt", timeout=1)
    assert payload.get("diagnoses"), payload
