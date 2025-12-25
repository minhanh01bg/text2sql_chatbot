from typing import TypedDict, Annotated, List, Dict, Any
from operator import add

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from app.prompts.intent_prompt import INTENT_CLASSIFICATION_PROMPT, CONSULTATION_PROMPT, COURSE_REGISTRATION_PROMPT, GENERAL_PROMPT
from app.schemas.intent_classifier import IntentClassifierSchema

try:
    from langchain_community.callbacks import get_openai_callback
except ImportError:
    from langchain.callbacks import get_openai_callback

from app.core.config import settings

import logging

logger = logging.getLogger(__name__)


class HitlGraphState(TypedDict):
    """State tối giản cho POC HITL."""

    messages: Annotated[List[Dict[str, str]], add]
    query: str
    intent: str  # Phân loại intent: general, consultation, course_registration
    draft_response: str
    suggested_actions: List[str]
    token_usage: Dict[str, Any]
    course_name: str  # Khóa học muốn đăng ký
    phone_number: str  # Số điện thoại học viên
    name: str  # Tên học viên
    email: str  # Email học viên


class HitlGraph:
    """Graph POC cho human-in-the-loop.

    Luồng:
        ingest_user_message -> classify_intent -> advisor -> await_human -> END
    """

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.7,
            openai_api_key=settings.openai_api_key,
        )
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(HitlGraphState)

        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("final_answer", self.final_answer)

        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "final_answer")
        workflow.add_edge("final_answer", END)


        # POC: chưa gắn checkpointer, mỗi call là một lượt độc lập (theo session_id ở service)
        return workflow.compile()

    

    async def _classify_intent(self, state: HitlGraphState) -> Dict[str, Any]:
        """Phân loại intent từ query của người dùng."""
        try:
            query = state.get("query", "")

            lc_messages = [
                SystemMessage(content=INTENT_CLASSIFICATION_PROMPT),
                HumanMessage(content=f"Câu hỏi: {query}"),
            ]

            with get_openai_callback() as cb:
                llm_with_structured = self.llm.with_structured_output(
                    IntentClassifierSchema
                )
                response = await llm_with_structured.ainvoke(lc_messages)
                intent = response.intent

                logger.info(f"Classified intent: {intent} for query: {query[:50]}...")

            return {"intent": intent}
        except Exception as e:
            logger.error(f"Error in HITL classify_intent: {e}")
            return {"intent": "general"}  # Fallback
    
    async def final_answer(self, state: HitlGraphState) -> Dict[str, Any]:
        """
        Tạo câu hỏi/response tiếp theo dựa trên intent và thông tin đã có trong state.

        - Nếu intent = course_registration:
            + Nếu chưa có thông tin khóa học trong state -> hỏi khóa học.
            + Nếu đã có khóa học nhưng chưa có số điện thoại -> hỏi số điện thoại.
        """
        intent = state.get("intent", "general")

        # Mặc định giữ lại draft_response hiện tại (nếu có)
        draft_response: str = state.get("draft_response", "")
        suggested_actions: List[str] = state.get("suggested_actions", []) or []
        token_usage: Dict[str, Any] = state.get("token_usage", {}).copy()

        if intent == "course_registration":
            # Tùy bạn sau này sẽ lưu khóa học dưới key nào, tạm hỗ trợ cả 2 cách đặt tên phổ biến
            course = state.get("course_name") or state.get("course")
            phone = state.get("phone_number")
            name = state.get("name")
            email = state.get("email")

            if not course:
                # Chưa biết học viên muốn đăng ký khóa nào -> hỏi thông tin khóa học
                draft_response = (
                    "Bạn muốn đăng ký khóa học nào? "
                    "Ví dụ: tên khóa, trình độ (cơ bản/nâng cao), hoặc mã khóa nếu bạn đã biết."
                )
                suggested_actions = ["ask_course_info"]
            else:
                missing_fields = []
                if not name:
                    missing_fields.append("họ tên")
                if not email:
                    missing_fields.append("email")
                if not phone:
                    missing_fields.append("số điện thoại")

                if missing_fields:
                    # Đã có khóa học nhưng thiếu một phần thông tin liên hệ -> hỏi riêng từng phần còn thiếu
                    fields_text = ", ".join(missing_fields)
                    draft_response = (
                        "Mình đã ghi nhận khóa học bạn muốn đăng ký. "
                        f"Bạn vui lòng cho mình xin {fields_text} để hoàn tất đăng ký nhé."
                    )

                    # Gợi ý action cụ thể theo thông tin còn thiếu
                    suggested_actions = []
                    if not name:
                        suggested_actions.append("ask_full_name")
                    if not email:
                        suggested_actions.append("ask_email")
                    if not phone:
                        suggested_actions.append("ask_phone_number")
        elif intent == "consultation":
            query = state.get("query", "")

            if not query:
                # Không có câu hỏi cụ thể -> yêu cầu người dùng mô tả rõ hơn nhu cầu tư vấn
                draft_response = (
                    "Bạn có thể cho mình biết rõ mục tiêu học hoặc kỹ năng bạn muốn cải thiện "
                    "để mình tư vấn lộ trình chi tiết hơn không?"
                )
                suggested_actions = ["ask_consultation_detail"]
            else:
                lc_messages = [
                    SystemMessage(content=CONSULTATION_PROMPT),
                    HumanMessage(content=query),
                ]

                try:
                    with get_openai_callback() as cb:
                        llm_response = await self.llm.ainvoke(lc_messages)
                        draft_response = llm_response.content

                        # Lưu lại token usage của lần tư vấn này
                        token_usage.update(
                            {
                                "prompt_tokens": cb.prompt_tokens,
                                "completion_tokens": cb.completion_tokens,
                                "total_tokens": cb.total_tokens,
                                "model": self.llm.model_name,
                                "cost": cb.total_cost,
                            }
                        )
                except Exception as e:
                    logger.error(f"Error generating consultation response: {e}")
                    draft_response = (
                        "Xin lỗi, mình đang gặp sự cố khi tư vấn. "
                        "Bạn có thể thử lại sau một chút nhé."
                    )
                    suggested_actions = ["error_retry"]
        elif intent == "general":
            query = state.get("query", "")

            if not query:
                draft_response = (
                    "Bạn muốn hỏi thêm thông tin gì? "
                    "Bạn có thể mô tả ngắn gọn để mình hỗ trợ nhé."
                )
                suggested_actions = ["ask_general_detail"]
            else:
                lc_messages = [
                    SystemMessage(content=GENERAL_PROMPT),
                    HumanMessage(content=query),
                ]

                try:
                    with get_openai_callback() as cb:
                        llm_response = await self.llm.ainvoke(lc_messages)
                        draft_response = llm_response.content

                        token_usage.update(
                            {
                                "prompt_tokens": cb.prompt_tokens,
                                "completion_tokens": cb.completion_tokens,
                                "total_tokens": cb.total_tokens,
                                "model": self.llm.model_name,
                                "cost": cb.total_cost,
                            }
                        )
                except Exception as e:
                    logger.error(f"Error generating general response: {e}")
                    draft_response = (
                        "Xin lỗi, mình đang gặp chút trục trặc nên chưa thể trả lời ngay. "
                        "Bạn vui lòng thử lại sau ít phút nhé."
                    )
                    suggested_actions = ["error_retry"]
        return {
            "draft_response": draft_response,
            "suggested_actions": suggested_actions,
            "token_usage": token_usage,
        }
    
hitl_graph = HitlGraph()



