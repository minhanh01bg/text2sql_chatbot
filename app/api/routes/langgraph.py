import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.services.graph_service import graph_service


router = APIRouter()


class IntentRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class IntentResponse(BaseModel):
    intent: str
    raw_query: str
    session_id: Optional[str] = None


@router.post("/")
async def classify_intent(request: IntentRequest):
    """
    Endpoint đơn giản để test graph (StateGraph) phân loại intent.

    Sử dụng `HitlGraph` đã compile + `graph_service.classify_intent`.
    Tự động tạo session_id nếu không được cung cấp để lưu log.
    """
    # Tự động tạo session_id nếu không có để đảm bảo luôn lưu log
    session_id = request.session_id or str(uuid.uuid4())
    
    result = await graph_service.classify_intent(request.message, session_id=session_id)
    
    # Thêm session_id vào response để client biết session_id đã dùng
    if isinstance(result, dict):
        result["session_id"] = session_id
    
    return result


