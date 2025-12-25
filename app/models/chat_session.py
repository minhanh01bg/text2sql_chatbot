from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token usage (tổng hoặc theo session)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: Optional[str] = None
    cost: float = 0.0


class ChatMessage(BaseModel):
    """Một lượt message trong session chat."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context: Optional[List[Dict[str, Any]]] = None
    knowledge_base_refs: Optional[List[str]] = None


class ChatSession(BaseModel):
    """
    Model: 1 document tương ứng 1 session_id.

    - Lưu toàn bộ lịch sử chat trong `messages`.
    - `token_usage` có thể là tổng token của cả session.
    """

    id: Optional[str] = Field(None, alias="_id")
    session_id: str
    messages: List[ChatMessage] = []
    token_usage: TokenUsage = Field(default_factory=TokenUsage)

    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


