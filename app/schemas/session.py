from datetime import datetime
from typing import Dict, Any, List

from pydantic import BaseModel

from app.models.chat_session import TokenUsage, ChatMessage


class SessionResponse(BaseModel):
    """
    Schema trả về cho 1 chat session.
    
    Một session chứa toàn bộ lịch sử chat trong messages,
    và token usage tổng của session.
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

