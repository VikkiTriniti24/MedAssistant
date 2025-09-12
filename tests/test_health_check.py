def test_health_check_happy_path(client, auth_headers):
    payload = {"symptoms": "fever 38.1, sore throat"}
    r = client.post("/health-check/", headers=auth_headers, json=payload)
    assert r.status_code == 200
    data = r.get_json()
    # Unterstützt sowohl {success,data} als auch plain payload:
    body = data.get("data", data)
    assert "summary" in body
    assert "diagnoses" in body
