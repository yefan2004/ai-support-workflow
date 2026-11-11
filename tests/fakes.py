"""测试用 AI Provider 假实现（不访问网络/数据库）。"""

import threading
from collections.abc import Callable

from app.core.triage_types import AllowedCategory, RiskLevel
from app.providers.ai.base import AIProvider, ClassificationResult


def make_result(
    *,
    category: AllowedCategory = AllowedCategory.PRODUCT_QUESTION,
    risk_level: RiskLevel = RiskLevel.LOW,
    summary: str = "测试摘要",
    risk_reason: str = "测试原因",
    requires_human: bool = True,
    draft_body: str | None = "您好，这是测试草稿。",
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        summary=summary,
        risk_level=risk_level,
        risk_reason=risk_reason,
        requires_human=requires_human,
        draft_body=draft_body,
    )


class RecordingProvider(AIProvider):
    """记录调用次数，可注入异常或在调用时执行回调。"""

    def __init__(
        self,
        result: ClassificationResult | None = None,
        error: Exception | None = None,
        on_classify: Callable[[], None] | None = None,
    ) -> None:
        self.result = result if result is not None else make_result()
        self.error = error
        self.on_classify = on_classify
        self.calls = 0
        self._lock = threading.Lock()

    def classify(self, subject: str, body: str) -> ClassificationResult:
        with self._lock:
            self.calls += 1
        if self.on_classify is not None:
            self.on_classify()
        if self.error is not None:
            raise self.error
        return self.result


class InvalidOutputProvider(AIProvider):
    """返回不符合 schema 的输出，用于验证失败分支。"""

    def classify(self, subject: str, body: str) -> ClassificationResult:
        return {"category": "invalid_category"}  # type: ignore[return-value]
