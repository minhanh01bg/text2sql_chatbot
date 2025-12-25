from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field

from app.models.chat_session import ChatSession, ChatMessage, TokenUsage  # noqa: F401


class ApiLog(BaseModel):
    """
    Log riêng cho các request API (không trùng với chat session).

    Dùng để biết:
    - endpoint nào được gọi
    - input là gì
    - thành công hay lỗi, status code, error message,...
    """

    id: Optional[str] = Field(None, alias="_id")
    path: str
    method: str
    status_code: int
    success: bool

    request_body: Optional[Dict[str, Any]] = None
    request_query: Optional[Dict[str, Any]] = None
    response_body: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
