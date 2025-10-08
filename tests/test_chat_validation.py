def test_chat_requires_nonempty_list(client, auth_headers):
    r = client.post("/chat/", headers=auth_headers, json={"messages":[]})
    assert r.status_code == 400

def test_chat_item_shape(client, auth_headers):
    r = client.post("/chat/", headers=auth_headers, json={"messages":[{"role":"user"}]})
    assert r.status_code == 400

def test_chat_happy(client, auth_headers, monkeypatch):
    # mock ai_service.chat_raw to avoid network
    import health_app.services.ai_service as ai
    from health_app.routes import chat as chat_routes

    monkeypatch.setattr(ai, "chat_raw", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(chat_routes, "chat_raw", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(chat_routes, "is_stub_mode", lambda: True)
    r = client.post("/chat/", headers=auth_headers, json={"messages":[{"role":"user","content":"hi"}]})
    assert r.status_code == 200
    assert r.get_json()["message"] == "ok"


def test_chat_includes_profile_context(client, auth_headers, monkeypatch):
    from health_app.routes import chat as chat_routes

    # Update profile details to ensure context is available
    client.put("/profile/", headers=auth_headers, json={"age": 42, "sex": "female"})
    client.post("/profile/conditions/", headers=auth_headers, json={"name": "Hypertension"})
    client.post("/profile/allergies/", headers=auth_headers, json={"name": "Penicillin"})

    captured = {}

    def fake_chat_raw(*, messages, timeout, language=None):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(chat_routes, "chat_raw", fake_chat_raw)
    monkeypatch.setattr(chat_routes, "is_stub_mode", lambda: False)

    response = client.post(
        "/chat/",
        headers=auth_headers,
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 200
    assert "messages" in captured
    assert captured["messages"][1]["role"] == "system"
    assert "Age: 42" in captured["messages"][1]["content"]
    assert "Hypertension" in captured["messages"][1]["content"]


def test_chat_fallback_respects_language(client, auth_headers, monkeypatch):
    from health_app.routes import chat as chat_routes
    from health_app.services import ai_service

    def fake_chat_raw(*, messages, timeout, language=None):
        last_user = messages[-1]["content"] if messages else ""
        return ai_service._safe_fallback_text(last_user, reason="stub mode active", language=language)

    monkeypatch.setattr(chat_routes, "chat_raw", fake_chat_raw)
    monkeypatch.setattr(chat_routes, "is_stub_mode", lambda: True)

    resp_en = client.post(
        "/chat/",
        headers=auth_headers,
        json={"messages": [{"role": "user", "content": "help"}]},
    )
    assert resp_en.status_code == 200
    message_en = resp_en.get_json()["message"]
    assert "MedAssistant fallback response:" in message_en

    client.put(
        "/profile/preferences/",
        headers=auth_headers,
        json={"language": "de"},
    )

    resp_de = client.post(
        "/chat/",
        headers=auth_headers,
        json={"messages": [{"role": "user", "content": "hilfe"}]},
    )
    assert resp_de.status_code == 200
    message_de = resp_de.get_json()["message"]
    assert "MedAssistant-Notfallantwort:" in message_de
