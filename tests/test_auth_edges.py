def test_register_conflict(client):
    e = "dupe@example.com"
    client.post("/auth/register", json={"email": e, "password": "x"})
    r = client.post("/auth/register", json={"email": e.upper(), "password": "x"})
    assert r.status_code == 409

def test_register_validation(client):
    r = client.post("/auth/register", json={"email": "", "password": ""})
    assert r.status_code == 400

def test_login_bad_credentials(client):
    client.post("/auth/register", json={"email": "x@example.com", "password": "good"})
    r = client.post("/auth/login", json={"email": "x@example.com", "password": "bad"})
    assert r.status_code == 401
