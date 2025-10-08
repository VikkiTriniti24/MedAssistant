from http import HTTPStatus


def test_emergency_contact_crud(client, auth_headers):
    # ensure list starts empty
    resp = client.get("/profile/emergency-contacts/", headers=auth_headers)
    assert resp.status_code == HTTPStatus.OK
    assert resp.get_json()["data"] == []

    create_resp = client.post(
        "/profile/emergency-contacts/",
        headers=auth_headers,
        json={
            "name": "Taylor Emergency",
            "relationship": "Sibling",
            "phone": "+1-555-0101",
            "email": "taylor@example.com",
            "is_primary": True,
        },
    )
    assert create_resp.status_code == HTTPStatus.CREATED
    contact_id = create_resp.get_json()["data"]["id"]

    list_resp = client.get("/profile/emergency-contacts/", headers=auth_headers)
    contact_list = list_resp.get_json()["data"]
    assert len(contact_list) == 1
    assert contact_list[0]["is_primary"] is True

    update_resp = client.put(
        f"/profile/emergency-contacts/{contact_id}/",
        headers=auth_headers,
        json={"phone": "+1-555-9999", "is_primary": False},
    )
    assert update_resp.status_code == HTTPStatus.OK
    updated = update_resp.get_json()["data"]
    assert updated["phone"] == "+1-555-9999"
    assert updated["is_primary"] is False

    delete_resp = client.delete(
        f"/profile/emergency-contacts/{contact_id}/",
        headers=auth_headers,
    )
    assert delete_resp.status_code == HTTPStatus.OK

    final_resp = client.get("/profile/emergency-contacts/", headers=auth_headers)
    assert final_resp.get_json()["data"] == []
