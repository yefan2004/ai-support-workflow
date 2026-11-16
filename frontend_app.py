"""Streamlit pending-review inbox.

Shows tasks from ``GET /api/v1/emails`` and loads task details for review.
Defaults to local 8014; override with the ``API_BASE_URL`` environment variable.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.getenv(
    "API_BASE_URL", "http://127.0.0.1:8014"
).rstrip("/")
REVIEWER_ID = "local-reviewer"
REQUEST_TIMEOUT_SECONDS = 10.0

_DEFAULT_LANGUAGE = "en"
_LANGUAGE_OPTIONS = ("English", "中文")
_LANGUAGE_CODES = {"English": "en", "中文": "zh"}

_RISK_LABELS = {
    "en": {"low": "Low", "medium": "Medium", "high": "High"},
    "zh": {"low": "低", "medium": "中", "high": "高"},
}
_STATUS_LABELS = {
    "en": {
        "received": "Received",
        "processing": "Processing",
        "awaiting_review": "Pending Review",
        "approved": "Approved",
        "rejected": "Rejected",
        "human_takeover": "Human Takeover",
        "failed": "Failed",
    },
    "zh": {
        "received": "已接收",
        "processing": "处理中",
        "awaiting_review": "待审核",
        "approved": "已通过",
        "rejected": "已拒绝",
        "human_takeover": "人工接管",
        "failed": "处理失败",
    },
}
_REVIEW_LABELS = {
    "en": {
        "approve": "approved",
        "reject": "rejected",
        "takeover": "marked for human takeover",
    },
    "zh": {
        "approve": "已通过",
        "reject": "已拒绝",
        "takeover": "已转人工接管",
    },
}


_UI = {
    "en": {
        "language_label": "Language",
        "title": "Human Review Dashboard",
        "description": (
            "AI has classified the email and generated a draft. "
            "Select a task for human review."
        ),
        "pending_review": "Pending Review",
        "task_details": "Task Details",
        "status": "Status",
        "category": "Category",
        "risk_level": "Risk Level",
        "original_email": "Original Email (first 300 characters)",
        "ai_summary": "AI Summary",
        "ai_draft": "AI Draft (editable)",
        "approve": "Approve",
        "reject": "Reject",
        "takeover": "Takeover",
        "no_tasks": "No pending review tasks",
        "select_task": "Select a task from the list.",
        "select": "Select",
        "selected": "Selected",
        "list_error": "Unable to load pending reviews: {error}",
        "list_invalid": "The pending review response format is invalid.",
        "list_unavailable": "The pending review list is unavailable.",
        "details_error": "Unable to load task details: {error}",
        "details_invalid": "The task detail response format is invalid.",
        "not_reviewable": (
            "This task is not awaiting review and cannot be reviewed."
        ),
        "no_body": "(No email body)",
        "no_summary": "(No summary)",
        "edits_saved": "Edits will be saved with the review action.",
        "submitting": "Submitting review…",
        "review_failed": "Review failed: {error}",
        "approved_not_sent": (
            " Approved does not mean the email has been sent."
        ),
        "pending_count": "{count} pending review tasks",
        "pending_count_one": "1 pending review task",
        "task_label": "Task #{task_id}",
        "list_risk": "Task #{task_id} · Risk Level: {risk}",
        "detail_meta": (
            "Status: {status}  |  Category: {category}  |  "
            "Risk Level: {risk}"
        ),
        "body_suffix": "\n… (showing first 300 characters)",
        "review_success": (
            "Task #{task_id} has been {review_label}. "
            "Current status: {status}."
        ),
        "backend_unreachable": (
            "Unable to connect to the backend ({error_type})."
        ),
        "backend_unreadable": "The backend returned an unreadable response.",
        "disclaimer": (
            "reviewed_by is a demo identity and does not represent "
            "authenticated identity. Approved does not mean the email has "
            "been sent. This page does not send emails."
        ),
    },
    "zh": {
        "language_label": "语言",
        "title": "人工审核面板",
        "description": "AI 已完成邮件分类并生成草稿。请选择一封邮件进行人工审核。",
        "pending_review": "待审核",
        "task_details": "任务详情",
        "status": "状态",
        "category": "分类",
        "risk_level": "风险等级",
        "original_email": "原始邮件（前 300 字）",
        "ai_summary": "AI 摘要",
        "ai_draft": "AI 草稿（可编辑）",
        "approve": "通过",
        "reject": "拒绝",
        "takeover": "转人工",
        "no_tasks": "暂无待审核任务",
        "select_task": "请从列表中选择一封待审核邮件。",
        "select": "选择",
        "selected": "已选中",
        "list_error": "无法加载待审核列表：{error}",
        "list_invalid": "待审核列表响应格式无效。",
        "list_unavailable": "待审核列表暂不可用。",
        "details_error": "无法加载任务详情：{error}",
        "details_invalid": "任务详情响应格式无效。",
        "not_reviewable": "该任务当前不是待审核状态，无法审核。",
        "no_body": "（无正文）",
        "no_summary": "（无摘要）",
        "edits_saved": "编辑后的草稿将随审核动作保存。",
        "submitting": "正在提交审核…",
        "review_failed": "审核失败：{error}",
        "approved_not_sent": "审核通过不代表邮件已发送。",
        "pending_count": "共 {count} 封待审核邮件",
        "pending_count_one": "共 1 封待审核邮件",
        "task_label": "任务 #{task_id}",
        "list_risk": "任务 #{task_id} · 风险等级：{risk}",
        "detail_meta": (
            "状态：{status} ｜ 分类：{category} ｜ 风险等级：{risk}"
        ),
        "body_suffix": "\n…（仅展示前 300 字）",
        "review_success": (
            "任务 #{task_id} {review_label}。当前状态：{status}。"
        ),
        "backend_unreachable": "无法连接后端（{error_type}）。",
        "backend_unreadable": "后端返回了无法解析的响应。",
        "disclaimer": (
            "reviewed_by 为演示身份，不代表已认证身份。"
            "审核通过不代表邮件已发送。本页面不会发送邮件。"
        ),
    },
}


_HTTP_ERROR_MESSAGES = {
    "en": {
        400: "The request was invalid.",
        401: "Authentication is required.",
        403: "This action is not allowed.",
        404: "Task not found.",
        409: "The task state changed or the action is not allowed.",
        422: "The request was invalid.",
        503: "The backend is unavailable. Please try again.",
    },
    "zh": {
        400: "请求无效。",
        401: "需要身份验证。",
        403: "不允许执行此操作。",
        404: "任务不存在。",
        409: "任务状态已变化，或当前操作不被允许。",
        422: "请求参数无效。",
        503: "后端暂不可用，请稍后重试。",
    },
}

# Keep styling limited to the page shell, bordered task cards, and our
# keyed review buttons. Do not restyle every Streamlit widget globally.
_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background: #f3f5f7;
}
[data-testid="stSidebar"] {
    background: #eef1f5;
}
.block-container {
    max-width: 1180px;
    padding-top: 2.25rem;
    padding-bottom: 3rem;
}
[class*="st-key-task-card-"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 0.9rem 1rem;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
}
.st-key-review-approve button:not(:disabled) {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
}
.st-key-review-approve button:not(:disabled):hover {
    background: #1d4ed8;
    border-color: #1d4ed8;
}
.st-key-review-reject button:not(:disabled) {
    background: #b45309;
    border-color: #b45309;
    color: #ffffff;
}
.st-key-review-reject button:not(:disabled):hover {
    background: #92400e;
    border-color: #92400e;
}
.st-key-review-takeover button:not(:disabled) {
    background: #475569;
    border-color: #475569;
    color: #ffffff;
}
.st-key-review-takeover button:not(:disabled):hover {
    background: #334155;
    border-color: #334155;
}
</style>
"""


def _http_error_message(status_code: int, language: str) -> str:
    fallback = (
        f"Request failed (HTTP {status_code})."
        if language == "en"
        else f"请求失败（HTTP {status_code}）。"
    )
    return _HTTP_ERROR_MESSAGES.get(language, {}).get(status_code, fallback)


def _request(
    method: str,
    path: str,
    *,
    language: str = _DEFAULT_LANGUAGE,
    **kwargs: Any,
) -> tuple[Any | None, str | None]:
    """Request the FastAPI backend and return (payload, error)."""
    t = _UI[language]
    try:
        response = httpx.request(
            method,
            f"{API_BASE_URL}{path}",
            timeout=REQUEST_TIMEOUT_SECONDS,
            **kwargs,
        )
    except httpx.HTTPError as exc:
        return None, t["backend_unreachable"].format(
            error_type=type(exc).__name__
        )

    if response.status_code >= 400:
        return None, _http_error_message(response.status_code, language)

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if payload is None:
        return None, t["backend_unreadable"]
    return payload, None


def _risk_label(value: Any, language: str) -> str:
    if not isinstance(value, str) or not value:
        return "—"
    label = _RISK_LABELS.get(language, {}).get(value)
    return f"{label} ({value})" if label else value


def _status_label(value: Any, language: str) -> str:
    if not isinstance(value, str) or not value:
        return "—"
    label = _STATUS_LABELS.get(language, {}).get(value)
    return f"{label} ({value})" if label else value


def _short_summary(task: dict[str, Any], language: str) -> str:
    summary = task.get("summary")
    text = str(summary) if summary else _UI[language]["no_summary"]
    text = " ".join(text.split())
    if len(text) > 44:
        text = text[:44] + "…"
    return text


def _set_flash(kind: str, message: str) -> None:
    st.session_state["flash_message"] = (kind, message)


def _show_flash() -> None:
    flash = st.session_state.pop("flash_message", None)
    if not flash:
        return
    kind, message = flash
    if kind == "success":
        st.success(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)


def _submit_review(
    task_id: int,
    action: str,
    draft_body: str,
    language: str,
) -> None:
    """Submit one review request without automatic retries."""
    t = _UI[language]
    payload = {
        "action": action,
        "reviewed_by": REVIEWER_ID,
        "review_comment": None,
        "draft_body": draft_body,
    }
    with st.spinner(t["submitting"]):
        result, error = _request(
            "POST",
            f"/api/v1/emails/{task_id}/review",
            language=language,
            json=payload,
        )

    if error:
        _set_flash("error", t["review_failed"].format(error=error))
    else:
        status = result.get("status") if isinstance(result, dict) else None
        message = t["review_success"].format(
            task_id=task_id,
            review_label=_REVIEW_LABELS[language][action],
            status=_status_label(status, language),
        )
        if action == "approve":
            message += t["approved_not_sent"]
        _set_flash("success", message)
        st.session_state.selected_task_id = None

    st.rerun()


st.set_page_config(
    page_title="Human Review Dashboard",
    page_icon="📥",
    layout="wide",
)

st.markdown(_CSS, unsafe_allow_html=True)

language_option = st.sidebar.radio(
    "Language / 语言",
    _LANGUAGE_OPTIONS,
    index=0,
    key="ui_language",
)
language = _LANGUAGE_CODES[language_option]
t = _UI[language]

st.title(t["title"])
st.caption(t["description"])
_show_flash()

if "selected_task_id" not in st.session_state:
    st.session_state.selected_task_id = None

tasks, list_error = _request("GET", "/api/v1/emails", language=language)
waiting_tasks: list[dict[str, Any]] = []
if list_error:
    st.error(t["list_error"].format(error=list_error))
elif not isinstance(tasks, list):
    st.error(t["list_invalid"])
else:
    waiting_tasks = [
        task
        for task in tasks
        if isinstance(task, dict) and task.get("status") == "awaiting_review"
    ]

selected_id = st.session_state.selected_task_id
if (
    not list_error
    and isinstance(tasks, list)
    and selected_id is not None
    and selected_id not in {
        task.get("id") for task in waiting_tasks
    }
):
    st.session_state.selected_task_id = None
    selected_id = None

left, right = st.columns([1, 2], gap="large")

with left:
    st.subheader(t["pending_review"])
    if list_error:
        st.caption(t["list_unavailable"])
    elif not waiting_tasks:
        st.info(t["no_tasks"])
    else:
        count = len(waiting_tasks)
        count_text = (
            t["pending_count_one"]
            if count == 1
            else t["pending_count"].format(count=count)
        )
        st.caption(count_text)
        for task in waiting_tasks:
            task_id = task.get("id")
            if not isinstance(task_id, int):
                continue
            with st.container(
                border=True, key=f"task-card-{task_id}"
            ):
                st.caption(
                    t["list_risk"].format(
                        task_id=task_id,
                        risk=_risk_label(task.get("risk_level"), language),
                    )
                )
                st.text(_short_summary(task, language))
                is_selected = task_id == selected_id
                if st.button(
                    t["selected"] if is_selected else t["select"],
                    key=f"select-task-{task_id}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state.selected_task_id = task_id
                    st.rerun()

with right:
    if selected_id is None:
        st.info(t["select_task"])
    else:
        detail, detail_error = _request(
            "GET",
            f"/api/v1/emails/{selected_id}",
            language=language,
        )
        if detail_error:
            st.error(t["details_error"].format(error=detail_error))
        elif not isinstance(detail, dict):
            st.error(t["details_invalid"])
        else:
            task_id = detail.get("id")
            status = detail.get("status")
            can_review = status == "awaiting_review"
            updated_at = detail.get("updated_at") or ""

            st.subheader(t["task_details"])
            st.caption(t["task_label"].format(task_id=task_id))
            st.caption(
                t["detail_meta"].format(
                    status=_status_label(status, language),
                    category=detail.get("category") or "—",
                    risk=_risk_label(detail.get("risk_level"), language),
                )
            )
            if not can_review:
                st.warning(t["not_reviewable"])

            body = detail.get("body") or ""
            if not isinstance(body, str):
                body = str(body)
            body_preview = body[:300]
            if len(body) > 300:
                body_preview += t["body_suffix"]
            st.text_area(
                t["original_email"],
                value=body_preview or t["no_body"],
                height=180,
                disabled=True,
                key=f"body-{task_id}-{updated_at}",
            )

            summary = detail.get("summary") or t["no_summary"]
            st.text_area(
                t["ai_summary"],
                value=str(summary),
                height=100,
                disabled=True,
                key=f"summary-{task_id}-{updated_at}",
            )

            draft_value = detail.get("draft_body")
            draft_text = draft_value if isinstance(draft_value, str) else ""
            draft_key = f"draft-{task_id}-{updated_at}"
            if draft_key not in st.session_state:
                st.session_state[draft_key] = draft_text
            edited_draft = st.text_area(
                t["ai_draft"],
                key=draft_key,
                height=280,
            )
            st.caption(t["edits_saved"])

            approve_disabled = not can_review or not edited_draft.strip()
            button_cols = st.columns(3)
            if button_cols[0].button(
                t["approve"],
                key="review-approve",
                type="primary",
                use_container_width=True,
                disabled=approve_disabled,
            ):
                _submit_review(
                    task_id, "approve", edited_draft, language
                )
            if button_cols[1].button(
                t["reject"],
                key="review-reject",
                type="secondary",
                use_container_width=True,
                disabled=not can_review,
            ):
                _submit_review(
                    task_id, "reject", edited_draft, language
                )
            if button_cols[2].button(
                t["takeover"],
                key="review-takeover",
                type="secondary",
                use_container_width=True,
                disabled=not can_review,
            ):
                _submit_review(
                    task_id, "takeover", edited_draft, language
                )

            st.caption(t["disclaimer"])

