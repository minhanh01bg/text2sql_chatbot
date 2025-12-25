from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HitlChatRequest(BaseModel):
    """
    Request cho POC LangGraph HITL.

    - mode = "start": bắt đầu phiên mới (session_id có thể null)
    - mode = "resume": tiếp tục từ phiên cũ với user_action
    """

    message: str
    session_id: Optional[str] = None
    context: Optional[List[Dict[str, Any]]] = []
    mode: str = "start"  # "start" | "resume"
    user_action: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Tôi muốn tư vấn về việc học AI",
                "session_id": None,
                "context": [],
                "mode": "start",
                "user_action": None,
            }
        }


class HitlChatResponse(BaseModel):
    response: str
    session_id: str
    token_usage: Dict[str, Any]
    knowledge_base_refs: Optional[List[str]] = []
    suggested_actions: Optional[List[str]] = []
    intent: Optional[str] = None  # Phân loại intent
    hitl: Dict[str, Any] = {}

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Đây là gợi ý lộ trình học AI của bạn ...",
                "session_id": "session_abc123",
                "token_usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 80,
                    "total_tokens": 200,
                    "model": "gpt-4o-mini",
                    "cost": 0.004,
                },
                "knowledge_base_refs": [],
                "suggested_actions": [
                    "ask_followup",
                    "need_more_detail",
                    "change_topic",
                    "confirm",
                ],
                "intent": "consultation",
                "hitl": {
                    "can_resume": True,
                },
            }
        }