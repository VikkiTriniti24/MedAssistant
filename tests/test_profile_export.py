from http import HTTPStatus


def test_profile_export_anonymize_toggle(client, auth_headers):
    # Baseline non-anonymized export
    resp_plain = client.get("/profile/export/", headers=auth_headers)
    assert resp_plain.status_code == HTTPStatus.OK
    data_plain = resp_plain.get_json()["data"]
    assert data_plain["anonymized"] is False
    assert data_plain["user"]["email"].endswith("@example.com")

    resp_masked = client.get("/profile/export/?anonymize=true", headers=auth_headers)
    assert resp_masked.status_code == HTTPStatus.OK
    data_masked = resp_masked.get_json()["data"]
    assert data_masked["anonymized"] is True
    assert data_masked["user"]["email"] is None
    assert str(data_masked["user"]["id"]).startswith("user-")
    assert data_masked["user"]["created_at"].count("-") == 2  # truncated date format

    # Ensure emergency contacts can be masked once created
    client.post(
        "/profile/emergency-contacts/",
        headers=auth_headers,
        json={"name": "Alice", "phone": "+49123", "is_primary": True},
    )
    masked_with_contacts = client.get("/profile/export/?anonymize=true", headers=auth_headers)
    payload = masked_with_contacts.get_json()["data"]
    assert payload["emergency_contacts"][0]["name"].startswith("Contact ")
    assert payload["emergency_contacts"][0]["phone"] is None
