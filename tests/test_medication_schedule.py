def _create_medication(client, auth_headers):
    resp = client.post(
        "/profile/medications/",
        headers=auth_headers,
        json={
            "drug_name": "Ibuprofen",
            "dosage": "200mg",
            "started_at": "2025-01-01",
        },
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]["id"]


def test_create_medication_schedule(client, auth_headers):
    medication_id = _create_medication(client, auth_headers)

    payload = {
        "timezone": "UTC",
        "times": ["08:00", "20:00"],
        "days_of_week": ["monday", "wednesday", "friday"],
        "instructions": "Take with food",
        "reminders": {"email": True, "push": False, "sms": True},
    }

    resp = client.post(
        f"/profile/medications/{medication_id}/schedule/",
        headers=auth_headers,
        json=payload,
    )

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["times"] == ["08:00", "20:00"]
    assert set(data["days_of_week"]) == {"mon", "wed", "fri"}
    assert data["reminders"]["email"] is True

    # Fetch schedule
    get_resp = client.get(
        f"/profile/medications/{medication_id}/schedule/",
        headers=auth_headers,
    )
    assert get_resp.status_code == 200
    fetched = get_resp.get_json()["data"]
    assert fetched["instructions"] == "Take with food"


def test_schedule_validation_times(client, auth_headers):
    medication_id = _create_medication(client, auth_headers)

    resp = client.post(
        f"/profile/medications/{medication_id}/schedule/",
        headers=auth_headers,
        json={"times": ["25:00"]},
    )

    assert resp.status_code == 400
    assert "times" in resp.get_json()["error"]


def test_update_and_delete_schedule(client, auth_headers):
    medication_id = _create_medication(client, auth_headers)

    create = client.post(
        f"/profile/medications/{medication_id}/schedule/",
        headers=auth_headers,
        json={"times": ["09:00"], "timezone": "UTC"},
    )
    assert create.status_code == 201

    update = client.post(
        f"/profile/medications/{medication_id}/schedule/",
        headers=auth_headers,
        json={"times": ["09:00", "21:00"], "timezone": "UTC", "reminders": {"push": True}},
    )
    assert update.status_code == 200
    data = update.get_json()["data"]
    assert data["times"] == ["09:00", "21:00"]
    assert data["reminders"]["push"] is True

    delete = client.delete(
        f"/profile/medications/{medication_id}/schedule/",
        headers=auth_headers,
    )
    assert delete.status_code == 200

    missing = client.get(
        f"/profile/medications/{medication_id}/schedule/",
        headers=auth_headers,
    )
    assert missing.status_code == 404
