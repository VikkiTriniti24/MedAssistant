from datetime import datetime, timedelta

from health_app import db
from health_app.models import User, Profile, ChatSession, ChatMessage


def _ensure_session_with_messages(app) -> int:
    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        assert user is not None

        profile = Profile.query.filter_by(user_id=user.id).first()
        if not profile:
            profile = Profile(user_id=user.id)
            db.session.add(profile)
            db.session.commit()

        session = ChatSession(profile_id=profile.id)
        db.session.add(session)
        db.session.commit()

        messages = [
            ChatMessage(session_id=session.id, sender="user", message_text="I have a headache."),
            ChatMessage(session_id=session.id, sender="assistant", message_text="Make sure to rest and hydrate."),
        ]
        db.session.add_all(messages)
        db.session.commit()

        return session.id


def test_export_chat_session_json(client, app, auth_headers):
    session_id = _ensure_session_with_messages(app)

    resp = client.get(f"/chat/export?session_id={session_id}", headers=auth_headers)
    assert resp.status_code == 200

    payload = resp.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["session_id"] == session_id
    assert data["message_count"] == 2
    assert len(data["messages"]) == 2


def test_export_chat_session_text(client, app, auth_headers):
    session_id = _ensure_session_with_messages(app)

    resp = client.get(f"/chat/export?session_id={session_id}&format=txt", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("text/plain")

    body = resp.get_data(as_text=True)
    assert "User" in body and "Assistant" in body


def test_summarize_chat_session(client, app, auth_headers, monkeypatch):
    session_id = _ensure_session_with_messages(app)

    from health_app.routes import chat as chat_routes

    monkeypatch.setattr(chat_routes, "chat_raw", lambda *a, **k: "Overview: Mock summary")

    resp = client.post(
        "/chat/summarize",
        headers=auth_headers,
        json={"session_id": session_id, "max_messages": 5},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["session_id"] == session_id
    assert data["data"]["message_count"] <= 5
    assert data["data"]["summary"].startswith("Overview")


def test_follow_up_requires_context(client, auth_headers):
    resp = client.post("/chat/follow-ups", headers=auth_headers, json={})
    assert resp.status_code == 400


def test_follow_up_stub_suggestions(client, app, auth_headers, monkeypatch):
    session_id = _ensure_session_with_messages(app)

    from health_app.routes import chat as chat_routes

    monkeypatch.setattr(chat_routes, "is_stub_mode", lambda: True)

    resp = client.post(
        "/chat/follow-ups",
        headers=auth_headers,
        json={"session_id": session_id, "max_suggestions": 2},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    suggestions = payload["data"]["suggestions"]
    assert len(suggestions) == 2
    assert all(isinstance(item, str) and item for item in suggestions)


def test_follow_up_ai_parsing(client, app, auth_headers, monkeypatch):
    session_id = _ensure_session_with_messages(app)

    from health_app.routes import chat as chat_routes

    monkeypatch.setattr(chat_routes, "is_stub_mode", lambda: False)
    monkeypatch.setattr(chat_routes, "chat_raw", lambda *a, **k: '{"suggestions": ["Check in about symptom changes", "Discuss lifestyle factors"]}')

    resp = client.post(
        "/chat/follow-ups",
        headers=auth_headers,
        json={"session_id": session_id, "max_suggestions": 3},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    suggestions = payload["data"]["suggestions"]
    assert suggestions == ["Check in about symptom changes", "Discuss lifestyle factors"]


def test_export_chat_session_anonymize(client, app, auth_headers):
    session_id = _ensure_session_with_messages(app)

    json_resp = client.get(
        f"/chat/export?session_id={session_id}&format=json&anonymize=true",
        headers=auth_headers,
    )
    assert json_resp.status_code == 200
    payload = json_resp.get_json()["data"]
    assert payload["anonymized"] is True
    assert str(payload["session_id"]).startswith("session-")
    assert all("timestamp" not in msg for msg in payload["messages"])

    text_resp = client.get(
        f"/chat/export?session_id={session_id}&format=txt&anonymize=true",
        headers=auth_headers,
    )
    assert text_resp.status_code == 200
    body = text_resp.get_data(as_text=True)
    assert "[" not in body  # timestamps stripped


def test_prune_chat_history_cli(app, runner):
    with app.app_context():
        user = User(email="retention@example.com", hashed_pwd="x")
        db.session.add(user)
        db.session.flush()

        profile = Profile(user_id=user.id)
        db.session.add(profile)
        db.session.flush()

        old_session = ChatSession(
            profile_id=profile.id,
            created_at=datetime.utcnow() - timedelta(days=180),
        )
        db.session.add(old_session)
        db.session.flush()

        old_message = ChatMessage(
            session_id=old_session.id,
            sender="user",
            message_text="Old message",
            sent_at=datetime.utcnow() - timedelta(days=180),
        )
        db.session.add(old_message)

        fresh_session = ChatSession(profile_id=profile.id)
        db.session.add(fresh_session)
        db.session.flush()

        fresh_message = ChatMessage(
            session_id=fresh_session.id,
            sender="assistant",
            message_text="Recent reply",
            sent_at=datetime.utcnow(),
        )
        db.session.add(fresh_message)
        db.session.commit()

        old_session_id = old_session.id
        fresh_session_id = fresh_session.id

    result = runner.invoke(args=["prune-chat-history", "--days=90"])
    assert result.exit_code == 0
    assert "chat messages" in result.output

    with app.app_context():
        remaining_messages = ChatMessage.query.all()
        remaining_session_ids = {m.session_id for m in remaining_messages}
        assert fresh_session_id in remaining_session_ids
        assert all(msg.session_id != old_session_id for msg in remaining_messages)
        assert ChatSession.query.filter_by(id=old_session_id).count() == 0
        assert ChatSession.query.filter_by(id=fresh_session_id).count() == 1
