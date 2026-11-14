"""人工审核单页的路由与静态内容测试（不依赖数据库）。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ui_page_is_served_as_html() -> None:
    response = client.get("/ui")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_ui_page_contains_lookup_and_review_controls() -> None:
    html = client.get("/ui").text

    for element_id in (
        "task-id",
        "task-status",
        "task-category",
        "task-risk-level",
        "task-summary",
        "task-draft",
        "task-failure",
        "reviewed-by",
        "review-comment",
        "load-button",
    ):
        assert f'id="{element_id}"' in html

    for action in ("approve", "reject", "takeover"):
        assert f'data-action="{action}"' in html

    assert "/api/v1/emails/" in html
    assert "/review" in html
    assert "awaiting_review" in html
    assert "draft_body" in html


def test_ui_page_has_safe_demo_and_send_semantics_labels() -> None:
    html = client.get("/ui").text

    assert "reviewed_by 为自报演示身份" in html
    assert "不代表邮件已发送" in html
    assert "本页面不会发送邮件" in html


def test_ui_page_uses_text_content_and_has_no_remote_assets() -> None:
    html = client.get("/ui").text

    assert "textContent" in html
    assert "innerHTML" not in html
    assert "<script src=" not in html
    assert "https://" not in html
    assert "http://" not in html


def test_ui_page_is_not_part_of_openapi_schema() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/ui" not in paths
