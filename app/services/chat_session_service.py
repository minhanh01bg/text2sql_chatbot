from typing import List, Optional, Dict, Any

from bson import ObjectId

from app.core.database import get_database
from app.models.chat_session import ChatSession, TokenUsage, ChatMessage
import logging

logger = logging.getLogger(__name__)


class ChatSessionService:
    """
    Service riêng cho Chat Sessions.
    
    Collection trong Mongo: `chat_sessions`.
    Quản lý các session chat: 1 document / 1 session_id.
    """

    @property
    def collection(self):
        """Lazy-load collection to avoid initialization issues"""
        db = get_database()
        if db is None:
            raise RuntimeError(
                "Database not connected. Ensure connect_to_mongo() is called."
            )
        return db.chat_sessions

    async def create_session(self, session: ChatSession) -> str:
        """Tạo mới một session (thường ít dùng trực tiếp, ưu tiên append_interaction)."""
        try:
            session_dict = session.model_dump(exclude={"id"})
            result = await self.collection.insert_one(session_dict)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating chat session: {e}")
            raise

    async def append_interaction(
        self,
        session_id: str,
        user_query: str,
        response: str,
        context: Optional[List[Dict[str, Any]]] = None,
        knowledge_base_refs: Optional[List[str]] = None,
        token_usage_delta: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Thêm một lượt hỏi-đáp vào session.

        - Nếu chưa có session_id -> tạo document mới.
        - Nếu đã có -> append messages + cộng dồn token_usage.
        """
        try:
            now = ChatSession.__fields__["created_at"].default_factory()  # datetime.utcnow()

            # Chuẩn hoá delta token usage
            token_delta = TokenUsage(**(token_usage_delta or {}))

            # Tạo 2 messages: user & assistant
            user_msg = ChatMessage(
                role="user",
                content=user_query,
                context=context,
                knowledge_base_refs=knowledge_base_refs,
            )
            assistant_msg = ChatMessage(
                role="assistant",
                content=response,
                context=None,
                knowledge_base_refs=knowledge_base_refs,
            )

            # Upsert session
            # Lưu ý: Không set token_usage trong $setOnInsert để tránh conflict với $inc
            # $inc sẽ tự tạo các nested fields nếu chưa tồn tại
            update_doc: Dict[str, Any] = {
                "$setOnInsert": {
                    "session_id": session_id,
                    "created_at": now,
                },
                "$push": {"messages": {"$each": [user_msg.model_dump(), assistant_msg.model_dump()]}},
                "$set": {"updated_at": now},
                "$inc": {
                    "token_usage.prompt_tokens": token_delta.prompt_tokens,
                    "token_usage.completion_tokens": token_delta.completion_tokens,
                    "token_usage.total_tokens": token_delta.total_tokens,
                    "token_usage.cost": token_delta.cost,
                },
            }

            # Set model nếu có (dùng $set riêng để tránh conflict)
            if token_delta.model:
                update_doc.setdefault("$set", {})
                update_doc["$set"]["token_usage.model"] = token_delta.model

            # Xử lý metadata: dùng dot notation trong $set để merge với metadata cũ
            # Tránh conflict với $setOnInsert bằng cách không set toàn bộ metadata
            if metadata:
                update_doc.setdefault("$set", {})
                for k, v in metadata.items():
                    update_doc["$set"][f"metadata.{k}"] = v

            result = await self.collection.update_one(
                {"session_id": session_id}, update_doc, upsert=True
            )

            # Lấy lại document để trả về id
            doc = await self.collection.find_one({"session_id": session_id})
            return str(doc["_id"]) if doc else ""
        except Exception as e:
            logger.error(f"Error appending interaction to session: {e}")
            raise

    async def get_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Lấy session theo id document."""
        try:
            doc = await self.collection.find_one({"_id": ObjectId(session_id)})
            if doc:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
            return doc
        except Exception as e:
            logger.error(f"Error getting chat session by id: {e}")
            return None

    async def get_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Lấy đúng 1 session theo session_id."""
        try:
            doc = await self.collection.find_one({"session_id": session_id})
            if doc:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
            return doc
        except Exception as e:
            logger.error(f"Error getting chat session by session_id: {e}")
            return None

    async def get_all(
        self, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Lấy tất cả session (phân trang)."""
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
            logger.error(f"Error getting all chat sessions: {e}")
            return []


chat_session_service = ChatSessionService()

