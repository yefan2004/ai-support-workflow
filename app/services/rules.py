"""高风险规则检查。

规则服务只做判断：不访问数据库、不修改任务状态、不调用 AI、
不生成自动发送指令。规则未命中不代表邮件安全，后续草稿仍必须人工审核。

本规则基于精确关键词，可能漏判或误判，仅用于演示。
"""

import re
from dataclasses import dataclass
from typing import Final

from app.core.triage_types import AllowedCategory, RiskLevel

LEGAL_COMPLAINT_KEYWORDS: Final[tuple[str, ...]] = (
    "complaint",
    "compensation",
    "lawsuit",
    "lawyer",
    "legal",
    "投诉",
    "赔偿",
    "起诉",
    "律师",
)

REFUND_KEYWORDS: Final[tuple[str, ...]] = (
    "refund",
    "reimbursement",
    "chargeback",
    "退款",
    "退钱",
)

ORDER_CHANGE_KEYWORDS: Final[tuple[str, ...]] = (
    "change order",
    "modify order",
    "update order",
    "cancel order",
    "change address",
    "修改订单",
    "更改订单",
    "取消订单",
    "修改收货地址",
    "更改收货地址",
)

PAYMENT_ACCOUNT_CHANGE_KEYWORDS: Final[tuple[str, ...]] = (
    "change payment",
    "update payment",
    "payment method",
    "account permission",
    "update account",
    "change account",
    "reset password",
    "修改付款",
    "更改付款",
    "更换支付方式",
    "修改支付",
    "修改账户",
    "更改账户",
    "账户权限",
    "修改权限",
    "修改密码",
    "重置密码",
)


@dataclass(frozen=True)
class RuleEvaluation:
    """规则检查结果。

    ``requires_immediate_handoff`` 为 True 表示规则要求立即转人工、
    不进入 AI 分类；为 False 仅表示规则未要求立即转人工，不代表安全。
    """

    matched: bool
    risk_level: RiskLevel | None
    risk_reason: str
    suggested_category: AllowedCategory | None
    requires_immediate_handoff: bool
    matched_keywords: tuple[str, ...] = ()


def _keyword_present(text: str, keyword: str) -> bool:
    """英文关键词按单词边界匹配；中文关键词按子串匹配。"""
    if keyword.isascii():
        pattern = rf"\b{re.escape(keyword)}\b"
    else:
        pattern = re.escape(keyword)
    return re.search(pattern, text, re.IGNORECASE) is not None


def _matched_keywords(
    text: str, keywords: tuple[str, ...]
) -> tuple[str, ...]:
    return tuple(keyword for keyword in keywords if _keyword_present(text, keyword))


def evaluate_rules(subject: str, body: str) -> RuleEvaluation:
    """检查邮件主题与正文中的高风险规则。

    优先级：法律/投诉/赔偿 > 退款/拒付 > 订单修改 > 付款/账户权限修改。
    正文为空或仅包含空白字符时，直接要求立即转人工，且不进入 AI 分类。
    """
    if not body.strip():
        return RuleEvaluation(
            matched=True,
            risk_level=RiskLevel.MEDIUM,
            risk_reason=(
                "正文为空或仅包含空白字符，无法自动分流，需立即转人工处理。"
            ),
            suggested_category=AllowedCategory.OTHER,
            requires_immediate_handoff=True,
        )

    text = f"{subject}\n{body}"

    legal_keywords = _matched_keywords(text, LEGAL_COMPLAINT_KEYWORDS)
    if legal_keywords:
        return RuleEvaluation(
            matched=True,
            risk_level=RiskLevel.HIGH,
            risk_reason=(
                "命中法律/投诉/赔偿规则："
                f"{', '.join(legal_keywords)}；需立即转人工处理。"
            ),
            suggested_category=AllowedCategory.COMPLAINT,
            requires_immediate_handoff=True,
            matched_keywords=legal_keywords,
        )

    refund_keywords = _matched_keywords(text, REFUND_KEYWORDS)
    if refund_keywords:
        return RuleEvaluation(
            matched=True,
            risk_level=RiskLevel.HIGH,
            risk_reason=(
                "命中退款/拒付规则："
                f"{', '.join(refund_keywords)}；需立即转人工处理。"
            ),
            suggested_category=AllowedCategory.REFUND_REQUEST,
            requires_immediate_handoff=True,
            matched_keywords=refund_keywords,
        )

    order_change_keywords = _matched_keywords(text, ORDER_CHANGE_KEYWORDS)
    if order_change_keywords:
        return RuleEvaluation(
            matched=True,
            risk_level=RiskLevel.MEDIUM,
            risk_reason=(
                "命中订单修改请求："
                f"{', '.join(order_change_keywords)}；需立即转人工处理。"
            ),
            suggested_category=AllowedCategory.ORDER_INQUIRY,
            requires_immediate_handoff=True,
            matched_keywords=order_change_keywords,
        )

    account_change_keywords = _matched_keywords(
        text, PAYMENT_ACCOUNT_CHANGE_KEYWORDS
    )
    if account_change_keywords:
        return RuleEvaluation(
            matched=True,
            risk_level=RiskLevel.MEDIUM,
            risk_reason=(
                "命中付款/账户权限修改请求："
                f"{', '.join(account_change_keywords)}；需立即转人工处理。"
            ),
            suggested_category=AllowedCategory.OTHER,
            requires_immediate_handoff=True,
            matched_keywords=account_change_keywords,
        )

    return RuleEvaluation(
        matched=False,
        risk_level=None,
        risk_reason="未命中高风险规则；不代表邮件安全，生成内容仍需人工审核。",
        suggested_category=None,
        requires_immediate_handoff=False,
    )
