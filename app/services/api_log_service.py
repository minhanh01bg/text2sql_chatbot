from typing import Optional, Dict, Any, List

from bson import ObjectId
from app.core.database import get_database
from app.models.log import ApiLog
import logging

logger = logging.getLogger(__name__)


class ApiLogService:
    """
    Service riêng cho API logs.
    
    Collection: `api_logs`.
    Quản lý các log của API requests riêng biệt với chat sessions.
    """

    @property
    def collection(self):
        db = get_database()
        if db is None:
            raise RuntimeError(
                "Database not connected. Ensure connect_to_mongo() is called."
            )
        return db.api_logs

    async def log_request(
        self,
        path: str,
        method: str,
        status_code: int,
        success: bool,
        request_body: Optional[Dict[str, Any]] = None,
        request_query: Optional[Dict[str, Any]] = None,
        response_body: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Ghi log cho một lần gọi API.

        - path, method: endpoint và HTTP method.
        - status_code, success: trạng thái.
        - request_body, request_query: input từ client.
        - response_body: response trả về (có thể cắt gọn nếu quá lớn).
        """
        try:
            log_doc = ApiLog(
                path=path,
                method=method,
                status_code=status_code,
                success=success,
                request_body=request_body,
                request_query=request_query,
                response_body=response_body,
                error_message=error_message,
                metadata=metadata or {},
            ).model_dump(exclude={"id"})

            result = await self.collection.insert_one(log_doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error logging API request: {e}")
            # Không raise để tránh làm hỏng luồng API chính
            return ""

    async def get_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """Lấy API log theo id document."""
        try:
            doc = await self.collection.find_one({"_id": ObjectId(log_id)})
            if doc:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
            return doc
        except Exception as e:
            logger.error(f"Error getting API log by id: {e}")
            return None

    async def get_all(
        self, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Lấy tất cả API logs (phân trang)."""
        try:
            cursor = (
                self.collection.find()
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            results = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"Error getting all API logs: {e}")
            return []

    async def get_by_path(
        self, path: str, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Lấy API logs theo path."""
        try:
            cursor = (
                self.collection.find({"path": path})
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            results = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"Error getting API logs by path: {e}")
            return []


api_log_service = ApiLogService()

