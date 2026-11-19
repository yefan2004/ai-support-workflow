"""POST /api/v1/ai/triage 的 Mock 分诊测试（不依赖数据库）。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ai_triage_refund_request() -> None:
    response = client.post(
        "/api/v1/ai/triage",
        json={"subject": "退款申请", "body": "我要退订单12345"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"intent", "urgency", "confidence", "summary"}
    assert payload["intent"] == "refund"
    assert payload["urgency"] == "high"
    assert 0.0 <= payload["confidence"] <= 1.0
    assert payload["summary"]


def test_ai_triage_inquiry_request() -> None:
    response = client.post(
        "/api/v1/ai/triage",
        json={"subject": "产品咨询", "body": "请问这款电机支持48V吗？"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "inquiry"
    assert payload["urgency"] == "low"
    assert 0.0 <= payload["confidence"] <= 1.0


def test_ai_triage_exchange_request() -> None:
    response = client.post(
        "/api/v1/ai/triage",
        json={"subject": "换货", "body": "尺码小了"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "exchange"
    assert payload["urgency"] == "medium"
    assert 0.0 <= payload["confidence"] <= 1.0
    assert payload["summary"]


def test_ai_triage_empty_request_uses_defaults() -> None:
    response = client.post("/api/v1/ai/triage", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "other"
    assert payload["urgency"] == "low"
    assert 0.0 <= payload["confidence"] <= 1.0
    assert payload["summary"]


def test_ai_triage_route_is_registered_once() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/ai/triage" in paths
    assert "/api/v1/api/v1/ai/triage" not in paths
