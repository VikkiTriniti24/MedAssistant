def test_register_and_login(client):
    strong_pwd = "StrongPass123"
    r1 = client.post("/auth/register", json={"email": "u1@example.com", "password": strong_pwd})
    assert r1.status_code in (200, 201)

    r2 = client.post("/auth/login", json={"email": "u1@example.com", "password": strong_pwd})
    assert r2.status_code == 200
    data = r2.get_json()
    assert "access_token" in data
    assert "email_verified" in data
