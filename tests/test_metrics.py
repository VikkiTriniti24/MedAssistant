from http import HTTPStatus


from health_app.metrics import reset_metrics, track_ai_fallback, track_rate_limit_hit


def test_metrics_endpoint_reports_counters(app, client):
    reset_metrics()
    with app.app_context():
        track_ai_fallback("de", "stub mode active")
        track_rate_limit_hit("auth-login", "user")

    resp = client.get("/metrics")
    assert resp.status_code == HTTPStatus.OK
    body = resp.get_data(as_text=True)
    assert "medassistant_ai_fallback_total{language=\"de\",reason=\"stub mode active\"} 1" in body
    assert "medassistant_rate_limit_hit_total{action=\"auth-login\",role=\"user\"} 1" in body


def test_metrics_endpoint_empty(app, client):
    reset_metrics()
    resp = client.get("/metrics")
    assert resp.status_code == HTTPStatus.OK
    assert "no metrics" in resp.get_data(as_text=True)
