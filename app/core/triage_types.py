"""邮件分流共享类型：类别与风险等级。

规则服务与 AI Provider 共用该模块，避免循环导入和字符串散落。
"""

import enum


class AllowedCategory(str, enum.Enum):
    """允许的邮件分类。"""

    PRODUCT_QUESTION = "product_question"
    ORDER_INQUIRY = "order_inquiry"
    REFUND_REQUEST = "refund_request"
    COMPLAINT = "complaint"
    OTHER = "other"


class RiskLevel(str, enum.Enum):
    """允许的风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
