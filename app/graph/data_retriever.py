from typing import Optional
from langchain.retrievers.document_compressors import LLMListwiseRerank
from langchain.retrievers import ContextualCompressionRetriever
from langchain.tools.retriever import create_retriever_tool
from langchain_openai import ChatOpenAI
from langchain_core.vectorstores import VectorStore
from langchain_community.vectorstores import FAISS

from app.core.config import settings
from app.graph.load_schema_embeddings import create_vectorstore_from_embeddings
import logging

logger = logging.getLogger(__name__)


class DataRetriever:
    """Helper class quản lý data retriever cho node retriever bảng trong graph."""

    def __init__(
        self,
        data_vectorstore: Optional[VectorStore] = None,
        llm: Optional[ChatOpenAI] = None,
        schema_doc_id: Optional[str] = None,
        auto_load_embeddings: bool = True,
    ):
        """
        Args:
            data_vectorstore: Vectorstore chứa thông tin về database schema/tables.
                Nếu None và auto_load_embeddings=True, sẽ tự động load từ MongoDB.
            llm: LLM instance để dùng cho reranking
            schema_doc_id: ID của schema document để load embeddings.
                Nếu None, sẽ load embeddings mới nhất.
            auto_load_embeddings: Nếu True, tự động load embeddings từ MongoDB nếu
                data_vectorstore là None.
        """
        self.llm = llm or ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.7,
            openai_api_key=settings.openai_api_key,
        )
        
        # Nếu không có vectorstore và auto_load=True, thử load từ MongoDB
        if data_vectorstore is None and auto_load_embeddings:
            try:
                # Import ở đây để tránh circular import
                import asyncio
                
                # Tạo event loop nếu chưa có
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Load vectorstore từ MongoDB
                if loop.is_running():
                    # Nếu đang trong async context, cần dùng create_task hoặc await
                    logger.warning(
                        "Event loop đang chạy, không thể load embeddings đồng bộ. "
                        "Sử dụng load_vectorstore_async() hoặc truyền data_vectorstore trực tiếp."
                    )
                    self.data_vectorstore = None
                else:
                    self.data_vectorstore = loop.run_until_complete(
                        create_vectorstore_from_embeddings(schema_doc_id=schema_doc_id)
                    )
                    if self.data_vectorstore:
                        logger.info("Đã load vectorstore từ MongoDB embeddings")
                    else:
                        logger.warning("Không thể load vectorstore từ MongoDB embeddings")
            except Exception as e:
                logger.warning(f"Không thể tự động load embeddings từ MongoDB: {e}")
                self.data_vectorstore = None
        else:
            self.data_vectorstore = data_vectorstore
    
    @classmethod
    async def create_with_embeddings(
        cls,
        schema_doc_id: Optional[str] = None,
        llm: Optional[ChatOpenAI] = None,
    ) -> "DataRetriever":
        """
        Factory method để tạo DataRetriever với embeddings từ MongoDB (async).
        
        Args:
            schema_doc_id: ID của schema document. Nếu None, load embeddings mới nhất.
            llm: LLM instance để dùng cho reranking
            
        Returns:
            DataRetriever instance với vectorstore đã được load
        """
        vectorstore = await create_vectorstore_from_embeddings(schema_doc_id=schema_doc_id)
        return cls(data_vectorstore=vectorstore, llm=llm, auto_load_embeddings=False)

    def get_data_retriever(self) -> Optional[ContextualCompressionRetriever]:
        """
        Tạo compression retriever từ data_vectorstore với reranking.
        
        Returns:
            ContextualCompressionRetriever hoặc None nếu không có vectorstore
        """
        retriever = (
            self.data_vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs={"k": 50, "lambda_mult": 0.25}
            )
            if self.data_vectorstore
            else None
        )

        if retriever is None:
            logger.warning("Data vectorstore is None, cannot create retriever")
            return None

        # Sử dụng LLMListwiseRerank để rerank kết quả
        compressor = LLMListwiseRerank.from_llm(llm=self.llm, top_n=10)

        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=retriever
        )

        return compression_retriever

    def get_data_retriever_tool(self):
        """
        Tạo retriever tool từ data retriever để dùng trong agent/tool calling.
        
        Returns:
            Tool từ create_retriever_tool hoặc None
        """
        retriever = self.get_data_retriever()
        if retriever is None:
            logger.warning("Cannot create data retriever tool: retriever is None")
            return None

        return create_retriever_tool(
            retriever,
            name="data_retriever",
            description=(
                "Use this tool to search and retrieve information about database tables, "
                "schemas, and table structures. This helps understand what data is available "
                "in the database for generating SQL queries."
            ),
            response_format="content_and_artifact",
        )

