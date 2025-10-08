from http import HTTPStatus


def test_family_member_crud(client, auth_headers):
    resp = client.get("/profile/family-members/", headers=auth_headers)
    assert resp.status_code == HTTPStatus.OK
    assert resp.get_json()["data"] == []

    create = client.post(
        "/profile/family-members/",
        headers=auth_headers,
        json={
            "name": "Jamie Doe",
            "relationship": "Spouse",
            "birthdate": "1990-01-01",
            "notes": "Emergency backup",
            "share_preferences": True,
        },
    )
    assert create.status_code == HTTPStatus.CREATED
    member_id = create.get_json()["data"]["id"]

    update = client.put(
        f"/profile/family-members/{member_id}/",
        headers=auth_headers,
        json={"notes": "Primary caregiver", "share_preferences": False},
    )
    assert update.status_code == HTTPStatus.OK
    updated = update.get_json()["data"]
    assert updated["notes"] == "Primary caregiver"
    assert updated["share_preferences"] is False

    delete_resp = client.delete(
        f"/profile/family-members/{member_id}/",
        headers=auth_headers,
    )
    assert delete_resp.status_code == HTTPStatus.OK

    final = client.get("/profile/family-members/", headers=auth_headers)
    assert final.get_json()["data"] == []
