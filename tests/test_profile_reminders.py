from datetime import datetime


def test_get_reminders_empty(client, auth_headers):
    resp = client.get("/profile/reminders/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["count"] == 0


def test_get_reminders_with_schedule(client, auth_headers):
    med_resp = client.post(
        "/profile/medications/",
        headers=auth_headers,
        json={"drug_name": "Metformin", "dosage": "500 mg"},
    )
    assert med_resp.status_code == 201
    medication_id = med_resp.get_json()["data"]["id"]

    schedule_resp = client.post(
        f"/profile/medications/{medication_id}/schedule/",
        headers=auth_headers,
        json={
            "timezone": "UTC",
            "times": ["07:00", "19:00"],
            "start_date": datetime.utcnow().date().isoformat(),
            "reminders": {"email": True},
        },
    )
    assert schedule_resp.status_code == 201

    reminders_resp = client.get("/profile/reminders/", headers=auth_headers)
    assert reminders_resp.status_code == 200
    data = reminders_resp.get_json()["data"]
    assert data["count"] == 1
    reminder = data["reminders"][0]
    assert reminder["drug_name"] in {"Metformin", "metformin"}
    assert reminder["reminders"]["channels"]["email"] is True
    assert reminder["next_reminder_at"]
