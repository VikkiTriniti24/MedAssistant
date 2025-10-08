def test_register_conflict(client):
    e = "dupe@example.com"
    client.post("/auth/register", json={"email": e, "password": "Better123"})
    r = client.post("/auth/register", json={"email": e.upper(), "password": "Better123"})
    assert r.status_code == 409

def test_register_validation(client):
    r = client.post("/auth/register", json={"email": "", "password": ""})
    assert r.status_code == 400


def test_register_requires_strong_password(client):
    r_short = client.post("/auth/register", json={"email": "weak@example.com", "password": "short"})
    assert r_short.status_code == 400

    r_no_digit = client.post("/auth/register", json={"email": "weak2@example.com", "password": "NoDigits"})
    assert r_no_digit.status_code == 400

    r_no_letter = client.post("/auth/register", json={"email": "weak3@example.com", "password": "12345678"})
    assert r_no_letter.status_code == 400

def test_login_bad_credentials(client):
    client.post("/auth/register", json={"email": "x@example.com", "password": "Goodpass9"})
    r = client.post("/auth/login", json={"email": "x@example.com", "password": "bad"})
    assert r.status_code == 401
