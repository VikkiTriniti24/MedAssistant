def test_chat_requires_nonempty_list(client, auth_headers):
    r = client.post("/chat/", headers=auth_headers, json={"messages":[]})
    assert r.status_code == 400

def test_chat_item_shape(client, auth_headers):
    r = client.post("/chat/", headers=auth_headers, json={"messages":[{"role":"user"}]})
    assert r.status_code == 400

def test_chat_happy(client, auth_headers, monkeypatch):
    # mock ai_service.chat_raw to avoid network
    import health_app.services.ai_service as ai
    monkeypatch.setattr(ai, "chat_raw", lambda msgs: "ok")
    r = client.post("/chat/", headers=auth_headers, json={"messages":[{"role":"user","content":"hi"}]})
    assert r.status_code == 200
    assert r.get_json()["message"] == "ok"
