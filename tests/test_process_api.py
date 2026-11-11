"""POST /api/v1/emails/{id}/process 成功与规则分支测试（真实 PostgreSQL）。"""

import pytest
from fastapi.testclient import TestClient

from app.core.triage_types import AllowedCategory, RiskLevel
from tests.api_helpers import create_task
from tests.fakes import RecordingProvider, make_result


def test_rule_refund_handoff_skips_provider(
    api_client: TestClient, override_ai_provider
) -> None:
    provider = RecordingProvider()
    override_ai_provider(provider)
    task_id = create_task(
        api_client, subject="退款申请", body="我要退款"
    )

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "human_takeover"
    assert payload["category"] == AllowedCategory.REFUND_REQUEST.value
    assert payload["risk_level"] == RiskLevel.HIGH.value
    assert payload["requires_human"] is True
    assert payload["summary"] is None
    assert payload["draft_body"] is None
    assert payload["processed_at"] is not None
    assert provider.calls == 0


def test_empty_body_rule_handoff_skips_provider(
    api_client: TestClient, override_ai_provider
) -> None:
    provider = RecordingProvider()
    override_ai_provider(provider)
    task_id = create_task(api_client, subject="你好", body="   \n\t ")

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "human_takeover"
    assert payload["category"] == AllowedCategory.OTHER.value
    assert payload["risk_level"] == RiskLevel.MEDIUM.value
    assert "正文为空" in payload["risk_reason"]
    assert payload["draft_body"] is None
    assert provider.calls == 0


def test_normal_product_with_draft_awaits_review(
    api_client: TestClient, override_ai_provider
) -> None:
    provider = RecordingProvider(result=make_result())
    override_ai_provider(provider)
    task_id = create_task(api_client)

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "awaiting_review"
    assert payload["category"] == AllowedCategory.PRODUCT_QUESTION.value
    assert payload["risk_level"] == RiskLevel.LOW.value
    assert payload["requires_human"] is True
    assert payload["draft_body"] == "您好，这是测试草稿。"
    assert payload["processed_at"] is not None
    assert provider.calls == 1


def test_provider_high_risk_forces_handoff_without_draft(
    api_client: TestClient, override_ai_provider
) -> None:
    provider = RecordingProvider(
        result=make_result(
            risk_level=RiskLevel.HIGH,
            draft_body="这段草稿不应保留",
        )
    )
    override_ai_provider(provider)
    task_id = create_task(api_client)

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "human_takeover"
    assert payload["risk_level"] == RiskLevel.HIGH.value
    assert payload["draft_body"] is None


@pytest.mark.parametrize(
    "category",
    [AllowedCategory.REFUND_REQUEST, AllowedCategory.COMPLAINT],
)
def test_provider_refund_or_complaint_forces_handoff(
    api_client: TestClient,
    override_ai_provider,
    category: AllowedCategory,
) -> None:
    provider = RecordingProvider(
        result=make_result(
            category=category,
            risk_level=RiskLevel.HIGH,
            draft_body="这个高风险草稿不应保留",
        )
    )
    override_ai_provider(provider)
    task_id = create_task(api_client)

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "human_takeover"
    assert payload["category"] == category.value
    assert payload["draft_body"] is None


@pytest.mark.parametrize("draft_body", [None, "", "   "])
def test_normal_result_without_usable_draft_requires_handoff(
    api_client: TestClient,
    override_ai_provider,
    draft_body: str | None,
) -> None:
    provider = RecordingProvider(
        result=make_result(
            category=AllowedCategory.PRODUCT_QUESTION,
            risk_level=RiskLevel.LOW,
            draft_body=draft_body,
        )
    )
    override_ai_provider(provider)
    task_id = create_task(api_client)

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "human_takeover"
    assert payload["draft_body"] is None
    assert "草稿" in payload["risk_reason"]
    assert "人工" in payload["risk_reason"]
