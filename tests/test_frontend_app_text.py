"""Static UI text checks for the bilingual Streamlit dashboard."""

import ast
from pathlib import Path

SOURCE = Path("frontend_app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
STRING_CONSTANTS = [
    node.value
    for node in ast.walk(TREE)
    if isinstance(node, ast.Constant) and isinstance(node.value, str)
]
TEXT = " ".join(" ".join(STRING_CONSTANTS).split())


def _assigned_constant(name: str) -> object:
    for node in TREE.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} assignment not found")


def test_dashboard_defaults_to_english() -> None:
    assert _assigned_constant("_DEFAULT_LANGUAGE") == "en"
    assert _assigned_constant("_LANGUAGE_OPTIONS") == ("English", "中文")


def test_dashboard_uses_required_english_labels() -> None:
    required = (
        "Human Review Dashboard",
        "AI has classified the email and generated a draft. "
        "Select a task for human review.",
        "Pending Review",
        "Task Details",
        "Status",
        "Category",
        "Risk Level",
        "Original Email (first 300 characters)",
        "AI Summary",
        "AI Draft (editable)",
        "Approve",
        "Reject",
        "Takeover",
        "No pending review tasks",
        "Select a task from the list.",
        "reviewed_by is a demo identity and does not represent "
        "authenticated identity. Approved does not mean the email has been "
        "sent. This page does not send emails.",
    )

    for label in required:
        assert label in TEXT


def test_dashboard_provides_chinese_translations() -> None:
    required = (
        "人工审核面板",
        "待审核",
        "任务详情",
        "状态",
        "分类",
        "风险等级",
        "原始邮件（前 300 字）",
        "AI 摘要",
        "AI 草稿（可编辑）",
        "通过",
        "拒绝",
        "转人工",
        "暂无待审核任务",
        "请从列表中选择一封待审核邮件。",
        "审核通过不代表邮件已发送。",
    )

    for label in required:
        assert label in TEXT


def test_dashboard_does_not_reintroduce_task_id_inputs() -> None:
    assert "st.text_input" not in SOURCE
    assert "st.number_input" not in SOURCE


def test_selected_task_uses_neutral_button_style() -> None:
    assert 'type="primary" if is_selected' not in SOURCE
    assert SOURCE.count('key=f"select-task-{task_id}"') == 1
    assert SOURCE.count('type="secondary"') >= 2




def test_dashboard_has_limited_scoped_visual_styles() -> None:
    assert "st.markdown(_CSS, unsafe_allow_html=True)" in SOURCE
    assert '[data-testid="stAppViewContainer"]' in SOURCE
    assert '[class*="st-key-task-card-"]' in SOURCE
    assert 'key=f"task-card-{task_id}"' in SOURCE
    for key in ("review-approve", "review-reject", "review-takeover"):
        assert f'key="{key}"' in SOURCE
        assert f".st-key-{key} button:not(:disabled)" in SOURCE

