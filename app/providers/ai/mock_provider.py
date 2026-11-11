"""确定性 Mock AI Provider。

只使用关键词分类；不访问网络、不读取 API Key、不访问数据库、
不发送邮件。输出仅供演示，不代表真实模型能力。
``requires_human`` 始终为 True，所有草稿都必须经过人工审核。
"""

from app.core.triage_types import AllowedCategory, RiskLevel
from app.providers.ai.base import AIProvider, ClassificationResult

_COMPLAINT_KEYWORDS = (
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

_REFUND_KEYWORDS = (
    "refund",
    "reimbursement",
    "chargeback",
    "退款",
    "退钱",
)

_ORDER_KEYWORDS = (
    "order",
    "shipping",
    "delivery",
    "订单",
    "物流",
    "发货",
    "快递",
)

_PRODUCT_KEYWORDS = (
    "product",
    "feature",
    "price",
    "产品",
    "功能",
    "价格",
)

_PRODUCT_DRAFT = (
    "您好，感谢您的咨询。我们已收到您关于产品或功能的问题，"
    "人工客服会尽快进一步确认并回复您。"
)
_ORDER_DRAFT = (
    "您好，感谢您的咨询。我们已收到您的订单相关咨询，"
    "人工客服会尽快核实并回复您。"
)


def _keyword_present(text: str, keyword: str) -> bool:
    """英文关键词按单词边界匹配；中文关键词按子串匹配。"""
    import re

    if keyword.isascii():
        pattern = rf"\b{re.escape(keyword)}\b"
    else:
        pattern = re.escape(keyword)
    return re.search(pattern, text, re.IGNORECASE) is not None


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_keyword_present(text, keyword) for keyword in keywords)


def _result(
    *,
    category: AllowedCategory,
    risk_level: RiskLevel,
    summary: str,
    risk_reason: str,
    draft_body: str | None,
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        summary=summary,
        risk_level=risk_level,
        risk_reason=risk_reason,
        requires_human=True,
        draft_body=draft_body,
    )


class MockAIProvider(AIProvider):
    """离线、确定性的 Mock Provider。

    分类优先级：投诉/法律 > 退款/拒付 > 订单/物流 > 产品/功能 > 其他。
    邮件正文中的“忽略指令”等文本只是普通文本，不会被当作系统指令。
    """

    def classify(self, subject: str, body: str) -> ClassificationResult:
        text = f"{subject}\n{body}"

        if _has_any(text, _COMPLAINT_KEYWORDS):
            return _result(
                category=AllowedCategory.COMPLAINT,
                risk_level=RiskLevel.HIGH,
                summary="客户表达投诉、法律或赔偿诉求。",
                risk_reason="命中投诉/法律相关关键词，需人工审核。",
                draft_body=None,
            )

        if _has_any(text, _REFUND_KEYWORDS):
            return _result(
                category=AllowedCategory.REFUND_REQUEST,
                risk_level=RiskLevel.HIGH,
                summary="客户提出退款或拒付请求。",
                risk_reason="命中退款/拒付相关关键词，需人工审核。",
                draft_body=None,
            )

        if _has_any(text, _ORDER_KEYWORDS):
            return _result(
                category=AllowedCategory.ORDER_INQUIRY,
                risk_level=RiskLevel.LOW,
                summary="客户咨询订单或物流相关信息。",
                risk_reason="订单/物流咨询，需人工审核后再回复。",
                draft_body=_ORDER_DRAFT,
            )

        if _has_any(text, _PRODUCT_KEYWORDS):
            return _result(
                category=AllowedCategory.PRODUCT_QUESTION,
                risk_level=RiskLevel.LOW,
                summary="客户咨询产品或功能相关信息。",
                risk_reason="普通产品或功能咨询，需人工审核后再回复。",
                draft_body=_PRODUCT_DRAFT,
            )

        return _result(
            category=AllowedCategory.OTHER,
            risk_level=RiskLevel.LOW,
            summary="客户来信暂无法归类。",
            risk_reason="未识别明确类别，需人工审核。",
            draft_body=None,
        )
