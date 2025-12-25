from typing import Dict, Any, List, Optional
import logging

from app.graph import HitlGraph, HitlGraphState, hitl_graph
from app.services.chat_session_service import chat_session_service

logger = logging.getLogger(__name__)


class GraphService:
    """
    Service wrapper rất đơn giản để test phần phân loại intent trong `HitlGraph`.

    - Dùng trực tiếp node `_classify_intent` của graph (không chạy cả workflow).
    - Trả về intent và state để bạn dễ debug.
    """

    def _empty_state(self, query: str) -> HitlGraphState:
        return HitlGraphState(
            messages=[],          # chưa dùng tới
            query=query,
            intent="general",     # default
            draft_response="",
            suggested_actions=[],
            token_usage={},
            course_name="",
            phone_number="",
            name="",
            email="",
        )

    async def classify_intent(
        self, message: str, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gọi LLM (với `llm_with_structured` + `ClassifyIntentSchemas`) để phân loại intent.

        Returns:
            {
              "intent": "consultation" | "course_registration" | "general",
              "raw_query": <message gốc>
            }
        """
        try:
            state = self._empty_state(query=message)
            # Dùng graph đã compile để chạy node `classify_intent`
            final_state = await hitl_graph.graph.ainvoke(state)
            intent = final_state.get("intent", "general")

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

            return {
                "final_state": final_state,
                "raw_query": message,
                "intent": intent,
            }
        except Exception as e:
            logger.error(f"Error in GraphService.classify_intent: {e}")
            # Fallback an toàn
            return {
                "intent": "general",
                "raw_query": message,
                "error": str(e),
            }


graph_service = GraphService()


