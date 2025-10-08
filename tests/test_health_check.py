import pytest


pytestmark = pytest.mark.slow

def test_health_check_happy_path(client, auth_headers):
    payload = {"symptoms": "fever 38.1, sore throat"}
    r = client.post("/health-check/", headers=auth_headers, json=payload)
    assert r.status_code == 200
    data = r.get_json()
    # Unterstützt sowohl {success,data} als auch plain payload:
    body = data.get("data", data)
    assert "summary" in body
    assert "diagnoses" in body
    assert "differential_diagnosis" in body
    assert isinstance(body["differential_diagnosis"], list)
    assert body["differential_diagnosis"], "Expected differential diagnoses list"
    assert "body_systems" in body
    assert isinstance(body["body_systems"], list)
    assert "emergency_contact" in body
    severity = body["summary"].get("severity")
    assert isinstance(severity, dict)
    assert 0 <= severity["score"] <= 100
    assert severity["level"] in {"low", "moderate", "high", "critical"}


def test_health_check_severity_escalates_for_critical_signs(client, auth_headers):
    payload = {
        "symptoms": "Crushing chest pain and difficulty breathing",
        "age": 78,
        "onset": "sudden",
        "vitals": {"temp_c": 39.8, "hr": 132, "spo2": 88},
    }
    r = client.post("/health-check/", headers=auth_headers, json=payload)
    assert r.status_code == 200
    body = r.get_json()["data"]
    severity = body["summary"]["severity"]
    assert severity["level"] in {"high", "critical"}
    assert severity["score"] >= 65
    systems = {s["system"] for s in body.get("body_systems", [])}
    assert "cardiovascular" in systems or "respiratory" in systems


def test_health_check_persists_severity_snapshot(client, auth_headers):
    payload = {
        "symptoms": "Persistent dizziness and blurry vision",
        "age": 67,
    }

    response = client.post("/health-check/", headers=auth_headers, json=payload)
    assert response.status_code == 200
    api_payload = response.get_json()["data"]
    severity = api_payload["summary"]["severity"]

    profile_res = client.get("/profile/", headers=auth_headers)
    assert profile_res.status_code == 200
    profile_data = profile_res.get_json()["data"]
    history = profile_data["health_history"]
    assert history, "Expected a persisted symptom entry in profile history"

    stored = history[0]["severity"]
    assert stored is not None
    assert stored["score"] == severity["score"]
    assert stored["level"] == severity["level"]
    assert stored["factors"] == severity["factors"]
    assert stored["recorded_at"] is not None
    stored_systems = history[0].get("body_systems", [])
    assert isinstance(stored_systems, list)
