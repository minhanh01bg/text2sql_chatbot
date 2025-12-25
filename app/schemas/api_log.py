from datetime import datetime
from typing import Dict, Any, Optional

from pydantic import BaseModel


class ApiLogResponse(BaseModel):
    """
    Schema trả về cho 1 API log.
    
    Chứa thông tin về một lần gọi API:
    - Endpoint, method, status code
    - Request/response body
    - Error message nếu có
    """

    id: str
    path: str
    method: str
    status_code: int
    success: bool
    request_body: Optional[Dict[str, Any]] = None
    request_query: Optional[Dict[str, Any]] = None
    response_body: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True

