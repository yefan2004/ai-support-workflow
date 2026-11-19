"""AI 邮件分诊接口的请求与响应模型。"""

from pydantic import BaseModel, Field


class AITriageRequest(BaseModel):
    """Mock AI 分诊请求体。"""

    subject: str = Field(default="", description="邮件主题")
    body: str = Field(default="", description="邮件正文")


class AITriageResponse(BaseModel):
    """Mock AI 分诊结果。"""

    intent: str = Field(
        description=(
            "邮件意图：inquiry / complaint / refund / exchange / urgent / other"
        )
    )
    urgency: str = Field(description="紧急程度：high / medium / low")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度，0-1")
    summary: str = Field(description="分诊摘要")
