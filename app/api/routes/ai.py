"""Mock AI 邮件分诊接口。

当前不调用外部模型，只根据关键词返回确定性结果，便于先跑通链路。
"""

from fastapi import APIRouter

from app.schemas.ai import AITriageRequest, AITriageResponse

router = APIRouter(tags=["ai"])

# 简单关键词匹配，仅用于 Mock 分诊；真实模型接入后替换本模块即可。
_COMPLAINT_KEYWORDS = (
    "投诉",
    "赔偿",
    "起诉",
    "律师",
    "complaint",
    "compensation",
    "lawsuit",
    "legal",
)
_REFUND_KEYWORDS = ("退款", "退钱", "refund", "chargeback")
_EXCHANGE_KEYWORDS = ("换货", "换尺码", "exchange", "尺码", "size")
_URGENT_KEYWORDS = ("紧急", "尽快", "马上", "立即", "urgent", "asap")
_INQUIRY_KEYWORDS = (
    "咨询",
    "询问",
    "价格",
    "报价",
    "功能",
    "inquiry",
    "question",
    "pricing",
    "quote",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """返回 text 是否包含任意关键词（英文不区分大小写）。"""
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _result(
    intent: str,
    urgency: str,
    confidence: float,
    summary: str,
) -> AITriageResponse:
    return AITriageResponse(
        intent=intent,
        urgency=urgency,
        confidence=confidence,
        summary=summary,
    )


def _triage(subject: str, body: str) -> AITriageResponse:
    """根据关键词返回确定性 Mock 分诊结果。"""
    text = f"{subject}\n{body}".strip()

    if not text:
        return _result(
            "other",
            "low",
            0.3,
            "邮件主题和正文为空，Mock 无法判断意图。",
        )

    if _contains_any(text, _COMPLAINT_KEYWORDS):
        return _result(
            "complaint",
            "high",
            0.9,
            "客户表达投诉或法律诉求，建议立即人工介入。",
        )

    if _contains_any(text, _REFUND_KEYWORDS):
        return _result(
            "refund",
            "high",
            0.95,
            "客户提出退款请求，建议优先人工核实订单和退款条件。",
        )

    if _contains_any(text, _EXCHANGE_KEYWORDS):
        return _result(
            "exchange",
            "medium",
            0.9,
            "客户提出换货请求，建议人工确认尺码和库存。",
        )

    if _contains_any(text, _URGENT_KEYWORDS):
        return _result(
            "urgent",
            "high",
            0.85,
            "邮件包含紧急诉求，建议优先处理。",
        )

    if _contains_any(text, _INQUIRY_KEYWORDS):
        return _result(
            "inquiry",
            "low",
            0.9,
            "客户提出咨询，建议人工确认后回复。",
        )

    return _result(
        "other",
        "low",
        0.5,
        "暂未识别明确意图，建议人工查看。",
    )


@router.post(
    "/ai/triage",
    response_model=AITriageResponse,
    summary="Mock AI 邮件分诊",
)
def triage_email(payload: AITriageRequest) -> AITriageResponse:
    """根据 subject/body 关键词返回 Mock 分诊结果。"""
    return _triage(payload.subject, payload.body)
