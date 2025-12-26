from typing import TypedDict, Annotated, List, Dict, Any
from operator import add

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from app.prompts.intent_prompt import INTENT_CLASSIFICATION_PROMPT
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
        # workflow.add_node("final_answer", self.final_answer)

        workflow.set_entry_point("classify_intent")
        # workflow.add_edge("classify_intent", "final_answer")
        # workflow.add_edge("final_answer", END)


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
    
hitl_graph = HitlGraph()



