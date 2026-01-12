from typing import TypedDict, Annotated, List, Dict, Any, Optional
from operator import add

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langchain_core.documents import Document
from app.prompts.intent_prompt import INTENT_CLASSIFICATION_PROMPT
from app.prompts.sql_planning_prompt import SQL_PLANNING_SYSTEM_PROMPT, SQL_PLANNING_USER_PROMPT
from app.prompts.sql_generation_prompt import SQL_GENERATION_SYSTEM_PROMPT, SQL_GENERATION_USER_PROMPT
from app.prompts.sql_correction_prompt import (
    SQL_CORRECTION_SYSTEM_PROMPT,
    SQL_CORRECTION_USER_PROMPT,
)
from app.prompts.out_of_scope_prompt import (
    OUT_OF_SCOPE_SYSTEM_PROMPT,
    OUT_OF_SCOPE_USER_PROMPT,
)
from app.schemas.intent_classifier import IntentClassifierSchema
from app.schemas.sql_generation import SQLGenerationSchema
from app.schemas.sql_correction import SQLCorrectionSchema
from app.graph.data_retriever import DataRetriever
from app.graph.knowledge_base_retriever import KnowledgeBaseRetriever
from app.graph.schema_helper import get_table_schemas_from_retrieved_docs
from app.core.sql_database import get_sql_connector

try:
    from langchain_community.callbacks import get_openai_callback
except ImportError:
    from langchain.callbacks import get_openai_callback

from app.core.config import settings

import logging

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    """State cho Graph."""

    messages: Annotated[List[Dict[str, str]], add]
    query: str
    intent: str  # Phân loại intent: text2sql, out_of_scope
    draft_response: str
    suggested_actions: List[str]
    token_usage: Dict[str, Any]
    retrieved_docs: List[Document]  # Kết quả truy vấn từ data retriever
    sql_plan: str  # SQL reasoning plan từ node plan_sql
    sql_query: str  # SQL query được sinh ra từ node generate_sql
    sql_reason: str  # Lý do tại sao viết SQL như vậy từ node generate_sql
    corrected_sql: str  # SQL đã được node sql_correction sửa (nếu có)
    sql_correction_reason: str  # Giải thích cách sửa SQL
    has_retried: bool  # Đã retry thực thi SQL hay chưa
    sql_result: Any  # Kết quả thực thi SQL từ node execute_sql
    sql_error: Optional[str]  # Lỗi khi thực thi SQL (nếu có)
    sql_error_category: Optional[str]  # Nhóm lỗi SQL (syntax, table_not_found, ...)
    final_response: str  # Response cuối cùng được format từ node format_response


class Graph:
    """Graph chung cho xử lý intent và truy vấn dữ liệu.

    Luồng:
        classify_intent -> (text2sql) -> create_query -> plan_sql -> generate_sql -> execute_sql -> (format_response | sql_correction -> execute_sql) -> format_response -> END
        classify_intent -> (out_of_scope) -> handle_out_of_scope -> format_response -> END
    
    SQL Correction Flow:
        - Nếu execute_sql fail và lỗi thuộc nhóm retriable (table/column not found, syntax error, type mismatch)
          và chưa retry (has_retried=False), sẽ đi đến sql_correction
        - sql_correction sẽ sửa SQL và set has_retried=True
        - Sau đó quay lại execute_sql để thử lại với corrected_sql
        - Nếu vẫn fail hoặc đã retry rồi, đi thẳng đến format_response
    
    Out of Scope Flow:
        - Khi intent là out_of_scope, đi đến handle_out_of_scope
        - handle_out_of_scope sẽ retrieve từ knowledge base (nếu có kb_retriever)
        - Generate response từ retrieved context và user query
        - Đi đến format_response để trả về cho user
    """

    def __init__(
        self,
        data_retriever: Optional[DataRetriever] = None,
        kb_retriever: Optional[KnowledgeBaseRetriever] = None,
    ) -> None:
        self.llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.7,
            openai_api_key=settings.openai_api_key,
        )
        self.data_retriever = data_retriever
        self.kb_retriever = kb_retriever
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)

        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("create_query", self._create_query)
        workflow.add_node("plan_sql", self._plan_sql)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("sql_correction", self._sql_correction)
        workflow.add_node("handle_out_of_scope", self._handle_out_of_scope)
        workflow.add_node("format_response", self._format_response)

        workflow.set_entry_point("classify_intent")
        
        # Conditional edge: nếu intent là text2sql thì đi đến create_query, out_of_scope -> handle_out_of_scope
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_after_intent,
            {
                "text2sql": "create_query",
                "out_of_scope": "handle_out_of_scope",
            }
        )
        
        # Flow cho out_of_scope: handle_out_of_scope -> format_response -> END
        workflow.add_edge("handle_out_of_scope", "format_response")
        
        # Flow cho text2sql: create_query -> plan_sql -> generate_sql -> execute_sql -> (format_response | sql_correction) -> END
        workflow.add_edge("create_query", "plan_sql")
        workflow.add_edge("plan_sql", "generate_sql")
        workflow.add_edge("generate_sql", "execute_sql")
        
        # Conditional edge: nếu SQL fail và có thể retry -> sql_correction, ngược lại -> format_response
        workflow.add_conditional_edges(
            "execute_sql",
            self._route_after_execute_sql,
            {
                "format_response": "format_response",
                "sql_correction": "sql_correction",
            }
        )
        
        # Sau khi correction, retry lại execute_sql
        workflow.add_edge("sql_correction", "execute_sql")
        
        workflow.add_edge("format_response", END)

        # POC: chưa gắn checkpointer, mỗi call là một lượt độc lập (theo session_id ở service)
        return workflow.compile()
    
    def _route_after_intent(self, state: GraphState) -> str:
        """Routing sau khi phân loại intent."""
        intent = state.get("intent", "out_of_scope")
        return intent if intent in ["text2sql", "out_of_scope"] else "out_of_scope"
    
    def _should_retry_sql(self, state: GraphState) -> bool:
        """Quyết định có nên retry SQL bằng cách gọi sql_correction hay không.
        
        Returns:
            True nếu nên retry (chưa retry và lỗi thuộc nhóm retriable)
            False nếu không nên retry
        """
        # Nếu đã retry rồi thì không retry nữa
        if state.get("has_retried", False):
            return False
        
        # Nếu không có lỗi thì không cần retry
        sql_error = state.get("sql_error")
        if not sql_error:
            return False
        
        # Chỉ retry với các lỗi có thể sửa được (logic/syntax errors)
        category = state.get("sql_error_category", "")
        retriable_categories = [
            "table_or_column_not_found",
            "syntax_error",
            "type_mismatch",
        ]
        
        return category in retriable_categories
    
    def _route_after_execute_sql(self, state: GraphState) -> str:
        """Routing sau khi thực thi SQL.
        
        Returns:
            "format_response" nếu success hoặc không nên retry
            "sql_correction" nếu fail và nên retry
        """
        sql_error = state.get("sql_error")
        
        # Nếu không có lỗi, đi thẳng đến format_response
        if not sql_error:
            return "format_response"
        
        # Nếu có lỗi và nên retry, đi đến sql_correction
        if self._should_retry_sql(state):
            logger.info("Routing to sql_correction for retry")
            return "sql_correction"
        
        # Nếu có lỗi nhưng không nên retry, đi thẳng đến format_response
        logger.info("Routing to format_response (no retry)")
        return "format_response"

    def _extract_schema_context(self, retrieved_docs: List[Document]) -> Dict[str, Any]:
        """Lấy schema_doc_id và danh sách bảng từ retrieved_docs để log."""
        schema_doc_id = None
        tables: List[str] = []

        for doc in retrieved_docs or []:
            md = doc.metadata or {}
            if not schema_doc_id:
                schema_doc_id = md.get("schema_doc_id")

            table_name = md.get("table_name")
            table_schema = md.get("table_schema") or "public"
            if table_name:
                full_name = (
                    f"{table_schema}.{table_name}"
                    if table_schema and table_schema != "public"
                    else table_name
                )
                tables.append(full_name)

        # Loại bỏ trùng lặp, giữ thứ tự
        seen = set()
        unique_tables = []
        for t in tables:
            if t not in seen:
                seen.add(t)
                unique_tables.append(t)

        return {"schema_doc_id": schema_doc_id, "tables": unique_tables}

    def _categorize_sql_error(self, error_message: str) -> str:
        """Phân loại lỗi SQL phổ biến để log/quan sát."""
        msg = (error_message or "").lower()

        table_column_patterns = [
            "does not exist",
            "unknown table",
            "unknown column",
            "undefined table",
            "undefined column",
            "no such table",
            "no such column",
        ]
        syntax_patterns = [
            "syntax error",
            "parse error",
            "at or near",
            "sqlstate 42601",
        ]
        type_patterns = [
            "type mismatch",
            "cannot cast",
            "invalid input syntax",
            "data type mismatch",
            "sqlstate 42804",
        ]
        permission_patterns = [
            "permission denied",
            "access denied",
            "sqlstate 42501",
            "role",
            "not authorized",
            "connection refused",
            "could not connect",
            "timeout",
        ]

        if any(p in msg for p in table_column_patterns):
            return "table_or_column_not_found"
        if any(p in msg for p in syntax_patterns):
            return "syntax_error"
        if any(p in msg for p in type_patterns):
            return "type_mismatch"
        if any(p in msg for p in permission_patterns):
            return "permission_or_connection"
        return "other"

    

    async def _classify_intent(self, state: GraphState) -> Dict[str, Any]:
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
            logger.error(f"Error in Graph classify_intent: {e}")
            return {"intent": "out_of_scope"}  # Fallback
    
    async def _create_query(self, state: GraphState) -> Dict[str, Any]:
        """Truy vấn data từ database schema/tables sử dụng data retriever."""
        try:
            query = state.get("query", "")
            
            if not self.data_retriever:
                logger.warning("Data retriever is not initialized, skipping data retrieval")
                return {"retrieved_docs": []}
            
            retriever = self.data_retriever.get_data_retriever()
            if retriever is None:
                logger.warning("Data retriever is None, cannot retrieve documents")
                return {"retrieved_docs": []}
            
            # Truy vấn documents liên quan đến query
            retrieved_docs = await retriever.ainvoke(query)
            
            logger.info(
                f"Retrieved {len(retrieved_docs)} documents for query: {query[:50]}..."
            )
            
            return {"retrieved_docs": retrieved_docs}
        except Exception as e:
            logger.error(f"Error in Graph create_query: {e}", exc_info=True)
            return {"retrieved_docs": []}
    
    async def _plan_sql(self, state: GraphState) -> Dict[str, Any]:
        """Phân tích query và retrieved_docs để tạo SQL reasoning plan."""
        try:
            query = state.get("query", "")
            retrieved_docs = state.get("retrieved_docs", [])
            
            if not retrieved_docs:
                logger.warning("No retrieved docs available for SQL planning")
                return {"sql_plan": "Không có schema information để tạo kế hoạch SQL."}
            
            # Lấy CREATE TABLE statements từ MongoDB dựa trên retrieved_docs
            retrieved_schema = await get_table_schemas_from_retrieved_docs(retrieved_docs)
            
            if not retrieved_schema:
                logger.warning("Could not retrieve table schemas from MongoDB")
                return {"sql_plan": "Không thể lấy schema information từ database."}
            
            # Gọi LLM để tạo SQL plan
            lc_messages = [
                SystemMessage(content=SQL_PLANNING_SYSTEM_PROMPT),
                HumanMessage(content=SQL_PLANNING_USER_PROMPT.format(
                    user_query=query,
                    retrieved_schema=retrieved_schema
                )),
            ]
            
            with get_openai_callback() as cb:
                response = await self.llm.ainvoke(lc_messages)
                sql_plan = response.content
                
                logger.info(f"Generated SQL plan for query: {query[:50]}...")
                logger.debug(f"SQL Plan: {sql_plan[:200]}...")
            
            return {"sql_plan": sql_plan}
        except Exception as e:
            logger.error(f"Error in Graph plan_sql: {e}", exc_info=True)
            return {"sql_plan": f"Lỗi khi tạo SQL plan: {str(e)}"}
    
    async def _generate_sql(self, state: GraphState) -> Dict[str, Any]:
        """Sinh SQL query từ plan và schema."""
        try:
            query = state.get("query", "")
            sql_plan = state.get("sql_plan", "")
            retrieved_docs = state.get("retrieved_docs", [])
            
            if not sql_plan:
                logger.warning("No SQL plan available for SQL generation")
                return {"sql_query": ""}
            
            # Lấy CREATE TABLE statements từ MongoDB dựa trên retrieved_docs
            table_schema = await get_table_schemas_from_retrieved_docs(retrieved_docs)
            
            if not table_schema:
                logger.warning("Could not retrieve table schemas from MongoDB")
                return {"sql_query": ""}
            
            # Gọi LLM để sinh SQL với structured output
            lc_messages = [
                SystemMessage(content=SQL_GENERATION_SYSTEM_PROMPT),
                HumanMessage(content=SQL_GENERATION_USER_PROMPT.format(
                    user_query=query,
                    sql_plan=sql_plan,
                    table_schema=table_schema
                )),
            ]
            
            with get_openai_callback() as cb:
                llm_with_structured = self.llm.with_structured_output(
                    SQLGenerationSchema
                )
                response = await llm_with_structured.ainvoke(lc_messages)
                sql_query = response.sql.strip()
                sql_reason = response.reason
                
                # logger.info(f"Generated SQL query: {sql_query[:100]}...")
                # logger.debug(f"SQL generation reason: {sql_reason[:200]}...")
            
            # Khi generate xong SQL lần đầu, reset các field liên quan đến correction
            return {
                "sql_query": sql_query,
                "sql_reason": sql_reason,
                "corrected_sql": "",
                "sql_correction_reason": "",
                "has_retried": False,
            }
        except Exception as e:
            logger.error(f"Error in Graph generate_sql: {e}", exc_info=True)
            return {"sql_query": ""}

    async def _sql_correction(self, state: GraphState) -> Dict[str, Any]:
        """Sử dụng LLM để sửa SQL bị lỗi dựa trên error_message và schema (chưa nối vào flow)."""
        try:
            # Nếu đã retry rồi thì không sửa nữa (guard an toàn)
            if state.get("has_retried", False):
                logger.info("SQL correction skipped because has_retried=True")
                return {}

            sql_query = state.get("sql_query", "")
            sql_error = state.get("sql_error", "") or ""
            retrieved_docs = state.get("retrieved_docs", [])

            if not sql_query or not sql_error:
                logger.warning(
                    "SQL correction skipped because sql_query or sql_error is empty"
                )
                return {}

            # Lấy CREATE TABLE statements từ MongoDB để hỗ trợ sửa lỗi chính xác
            table_schema = await get_table_schemas_from_retrieved_docs(retrieved_docs)
            if not table_schema:
                logger.warning(
                    "SQL correction: could not retrieve table schemas from MongoDB"
                )
                return {}

            lc_messages = [
                SystemMessage(content=SQL_CORRECTION_SYSTEM_PROMPT),
                HumanMessage(
                    content=SQL_CORRECTION_USER_PROMPT.format(
                        table_schema=table_schema,
                        invalid_sql=sql_query,
                        error_message=sql_error,
                    )
                ),
            ]

            with get_openai_callback() as cb:
                llm_with_structured = self.llm.with_structured_output(
                    SQLCorrectionSchema
                )
                response = await llm_with_structured.ainvoke(lc_messages)
                corrected_sql = response.sql.strip()
                correction_reason = response.reason

            logger.info(
                "SQL correction generated successfully",
                extra={
                    "original_sql_preview": sql_query[:100],
                    "corrected_sql_preview": corrected_sql[:100],
                },
            )

            return {
                "corrected_sql": corrected_sql,
                "sql_correction_reason": correction_reason,
                "has_retried": True,
            }
        except Exception as e:
            logger.error(f"Error in Graph sql_correction: {e}", exc_info=True)
            # Nếu correction lỗi, không thay đổi state, để flow chính xử lý error như cũ
            return {}
    
    async def _execute_sql(self, state: GraphState) -> Dict[str, Any]:
        """Thực thi SQL query và lấy kết quả.
        
        Nếu có corrected_sql (từ node sql_correction), sẽ ưu tiên dùng corrected_sql.
        Nếu không có, dùng sql_query gốc.
        """
        try:
            sql_query = state.get("sql_query", "")
            corrected_sql = state.get("corrected_sql", "")
            sql_reason = state.get("sql_reason", "")
            retrieved_docs = state.get("retrieved_docs", [])
            # schema_ctx = self._extract_schema_context(retrieved_docs)
            
            # Ưu tiên dùng corrected_sql nếu có (từ node sql_correction)
            sql_to_execute = corrected_sql if corrected_sql else sql_query
            is_using_corrected = bool(corrected_sql)
            
            if not sql_to_execute:
                logger.warning("No SQL query to execute")
                return {"sql_result": None, "sql_error": "Không có SQL query để thực thi"}
            
            # Lấy SQL connector
            sql_connector = get_sql_connector()
            if sql_connector is None:
                logger.error("SQL connector is not available")
                return {"sql_result": None, "sql_error": "Không thể kết nối đến database"}
            
            # Log thông tin SQL sẽ thực thi
            if is_using_corrected:
                logger.info(
                    "Executing corrected SQL",
                    extra={
                        "original_sql_preview": sql_query[:100] if sql_query else "",
                        "corrected_sql_preview": corrected_sql[:100],
                    },
                )
            else:
                logger.info(
                    "Executing original SQL",
                    extra={"sql_preview": sql_to_execute[:100]},
                )
            
            # Thực thi SQL
            success, result, error = sql_connector.execute_query_safe(sql_to_execute)
            
            if success:
                logger.info(
                    "SQL executed successfully",
                    extra={
                        "result_type": str(type(result)),
                        "used_corrected_sql": is_using_corrected,
                        # "schema_doc_id": schema_ctx.get("schema_doc_id"),
                        # "tables": schema_ctx.get("tables"),
                    },
                )
                return {"sql_result": result, "sql_error": None}
            else:
                category = self._categorize_sql_error(error)
                logger.error(
                    "SQL execution failed",
                    extra={
                        "error": error,
                        "category": category,
                        "sql_query": sql_to_execute[:200] if sql_to_execute else "",
                        "sql_reason": sql_reason,
                        "used_corrected_sql": is_using_corrected,
                    },
                )
                return {"sql_result": None, "sql_error": error, "sql_error_category": category}
        except Exception as e:
            logger.error(f"Error in Graph execute_sql: {e}", exc_info=True)
            return {"sql_result": None, "sql_error": str(e)}
    
    async def _format_response(self, state: GraphState) -> Dict[str, Any]:
        """Format kết quả SQL để trả về user."""
        try:
            query = state.get("query", "")
            sql_query = state.get("sql_query", "")
            sql_result = state.get("sql_result")
            sql_error = state.get("sql_error")
            
            if sql_error:
                final_response = f"Xin lỗi, đã xảy ra lỗi khi thực thi truy vấn:\n{sql_error}\n\nSQL query: {sql_query}"
            elif sql_result is None:
                final_response = "Không thể lấy kết quả từ database."
            else:
                # Format kết quả
                if isinstance(sql_result, str):
                    # Nếu là string, có thể đã được format sẵn
                    final_response = sql_result
                elif isinstance(sql_result, (list, tuple)):
                    # Nếu là list/tuple, format thành bảng
                    if not sql_result:
                        final_response = "Không tìm thấy kết quả nào."
                    else:
                        # Format đơn giản
                        result_str = "\n".join([str(row) for row in sql_result[:50]])  # Limit 50 rows
                        if len(sql_result) > 50:
                            result_str += f"\n... (còn {len(sql_result) - 50} kết quả khác)"
                        final_response = f"Kết quả:\n{result_str}"
                else:
                    # Fallback: convert to string
                    final_response = str(sql_result)
            
            logger.info(f"Formatted response for query: {query[:50]}...")
            
            return {"final_response": final_response}
        except Exception as e:
            logger.error(f"Error in Graph format_response: {e}", exc_info=True)
            return {"final_response": f"Lỗi khi format response: {str(e)}"}
    
    async def _handle_out_of_scope(self, state: GraphState) -> Dict[str, Any]:
        """Xử lý câu hỏi out_of_scope bằng cách retrieve từ knowledge base và generate response."""
        try:
            query = state.get("query", "")
            
            if not query:
                logger.warning("No query provided for out_of_scope handling")
                return {"final_response": "Xin lỗi, tôi không hiểu câu hỏi của bạn."}
            
            # Retrieve từ knowledge base nếu có kb_retriever
            retrieved_context = ""
            if self.kb_retriever:
                try:
                    retriever = self.kb_retriever.get_kb_retriever()
                    if retriever:
                        retrieved_docs = await retriever.ainvoke(query)
                        if retrieved_docs:
                            # Format retrieved documents thành context string
                            context_parts = []
                            for doc in retrieved_docs:
                                context_parts.append(doc.page_content)
                            retrieved_context = "\n\n---\n\n".join(context_parts)
                            logger.info(
                                f"Retrieved {len(retrieved_docs)} documents from knowledge base "
                                f"for query: {query[:50]}..."
                            )
                        else:
                            logger.info("No relevant documents found in knowledge base")
                    else:
                        logger.warning("Knowledge base retriever is not available")
                except Exception as e:
                    logger.error(f"Error retrieving from knowledge base: {e}", exc_info=True)
                    # Continue without retrieved context
            else:
                logger.info("Knowledge base retriever not initialized, skipping retrieval")
            
            # Nếu không có retrieved context, vẫn trả lời nhưng thông báo không có thông tin
            if not retrieved_context:
                retrieved_context = "Không có thông tin liên quan trong knowledge base."
            
            # Gọi LLM để generate response
            lc_messages = [
                SystemMessage(content=OUT_OF_SCOPE_SYSTEM_PROMPT),
                HumanMessage(content=OUT_OF_SCOPE_USER_PROMPT.format(
                    user_query=query,
                    retrieved_context=retrieved_context,
                )),
            ]
            
            with get_openai_callback() as cb:
                response = await self.llm.ainvoke(lc_messages)
                final_response = response.content.strip()
                
                logger.info(f"Generated out_of_scope response for query: {query[:50]}...")
            
            return {"final_response": final_response}
        except Exception as e:
            logger.error(f"Error in Graph handle_out_of_scope: {e}", exc_info=True)
            return {"final_response": f"Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi của bạn: {str(e)}"}


graph = Graph()

