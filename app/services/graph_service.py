from typing import Dict, Any, List, Optional
import logging

from langchain_core.documents import Document
from app.graph import Graph, GraphState, graph
from app.services.chat_session_service import chat_session_service

logger = logging.getLogger(__name__)


class GraphService:
    """
    Service wrapper rất đơn giản để test phần phân loại intent trong `Graph`.

    - Dùng trực tiếp node `_classify_intent` của graph (không chạy cả workflow).
    - Trả về intent và state để bạn dễ debug.
    """

    def _empty_state(self, query: str) -> GraphState:
        return GraphState(
            messages=[],          # chưa dùng tới
            query=query,
            intent="out_of_scope",     # default
            draft_response="",
            suggested_actions=[],
            token_usage={},
            course_name="",
            phone_number="",
            name="",
            email="",
            retrieved_docs=[],  # Kết quả truy vấn từ data retriever
        )

    async def classify_intent(
        self, message: str, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gọi LLM (với `llm_with_structured` + `ClassifyIntentSchemas`) để phân loại intent.

        Returns:
            {
              "intent": "text2sql" | "out_of_scope",
              "raw_query": <message gốc>,
              "retrieved_docs": <danh sách documents nếu intent là text2sql>
            }
        """
        try:
            state = self._empty_state(query=message)
            # Dùng graph đã compile để chạy toàn bộ workflow
            final_state = await graph.graph.ainvoke(state)
            intent = final_state.get("intent", "out_of_scope")

            logger.info(f"[GraphService] intent={intent!r} for query={message[:80]!r}")

            # Lưu lại vào chat_sessions nếu có session_id
            if session_id:
                try:
                    await chat_session_service.append_interaction(
                        session_id=session_id,
                        user_query=message,
                        response=f"[intent_classification] intent={intent}",
                        context=None,
                        knowledge_base_refs=None,
                        token_usage_delta=None,  # POC: chưa lấy token usage chi tiết
                        metadata={"source": "graph_service.classify_intent"},
                    )
                    logger.info(f"[GraphService] Logged interaction for session {session_id}")
                except Exception as log_err:
                    # Không làm hỏng luồng chính nếu log lỗi
                    logger.error(
                        f"Error logging intent classification for session {session_id}: {log_err}",
                        exc_info=True
                    )
            else:
                logger.warning("[GraphService] No session_id provided, skipping log storage")

            retrieved_docs = final_state.get("retrieved_docs", [])
            
            return {
                "final_state": final_state,
                # "raw_query": message,
                # "intent": intent,
                # "retrieved_docs": retrieved_docs,
            }
        except Exception as e:
            logger.error(f"Error in GraphService.classify_intent: {e}")
            # Fallback an toàn
            return {
                "intent": "out_of_scope",
                "raw_query": message,
                "retrieved_docs": [],
                "error": str(e),
            }


graph_service = GraphService()


