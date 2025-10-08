import pytest


@pytest.mark.parametrize(
    "path",
    ["/", "/login", "/register", "/metrics"],
)
def test_security_headers_present(client, path):
    resp = client.get(path)

    assert resp.status_code < 500

    csp = resp.headers.get("Content-Security-Policy")
    assert csp, "CSP header missing"
    assert "script-src" in csp
    assert "'nonce-" in csp

    coop = resp.headers.get("Cross-Origin-Opener-Policy")
    corp = resp.headers.get("Cross-Origin-Resource-Policy")
    referrer = resp.headers.get("Referrer-Policy")

    assert coop == "same-origin"
    assert corp == "same-origin"
    assert referrer == "strict-origin-when-cross-origin"
