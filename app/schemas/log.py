from datetime import datetime
from typing import Dict, Any, List, Optional

from pydantic import BaseModel

from app.models.chat_session import TokenUsage, ChatMessage


class LogResponse(BaseModel):
    """
    Schema trả về cho 1 session (1 document trong collection mới).

    Giữ tên là LogResponse để không phải đổi route `/logs`,
    nhưng bên trong là thông tin cấp session.
    """

    id: str
    session_id: str
    messages: List[ChatMessage]
    token_usage: TokenUsage
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

