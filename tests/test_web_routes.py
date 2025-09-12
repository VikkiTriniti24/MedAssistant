def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"My Health App" in r.data  # aus base.html Header

def test_healthz(client):
    r = client.get("/healthz")
    j = r.get_json()
    assert r.status_code == 200
    assert j["ok"] is True
    assert "uptime_seconds" in j

def test_favicon_no_content(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 204

def test_login_page(client):
    r = client.get("/login")
    assert r.status_code == 200
