"""
Retriever cho knowledge base để dùng trong RAG khi intent là out_of_scope.
"""
from typing import Optional
from langchain.retrievers.document_compressors import LLMListwiseRerank
from langchain.retrievers import ContextualCompressionRetriever
from langchain_openai import ChatOpenAI
from langchain_core.vectorstores import VectorStore

from app.core.config import settings
from app.graph.load_knowledge_base_embeddings import create_knowledge_base_vectorstore
import logging

logger = logging.getLogger(__name__)


class KnowledgeBaseRetriever:
    """Helper class quản lý knowledge base retriever cho RAG khi out_of_scope."""

    def __init__(
        self,
        kb_vectorstore: Optional[VectorStore] = None,
        llm: Optional[ChatOpenAI] = None,
        source_id: Optional[str] = None,
        document_id: Optional[str] = None,
        auto_load_embeddings: bool = True,
    ):
        """
        Args:
            kb_vectorstore: Vectorstore chứa knowledge base embeddings.
                Nếu None và auto_load_embeddings=True, sẽ tự động load từ MongoDB.
            llm: LLM instance để dùng cho reranking
            source_id: Source ID để filter embeddings (nếu None, lấy tất cả)
            document_id: Document ID để filter embeddings (nếu None, lấy tất cả)
            auto_load_embeddings: Nếu True, tự động load embeddings từ MongoDB nếu
                kb_vectorstore là None.
        """
        self.llm = llm or ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.7,
            openai_api_key=settings.openai_api_key,
        )
        self.source_id = source_id
        self.document_id = document_id
        
        # Nếu không có vectorstore và auto_load=True, thử load từ MongoDB
        if kb_vectorstore is None and auto_load_embeddings:
            try:
                import asyncio
                
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                if loop.is_running():
                    logger.warning(
                        "Event loop đang chạy, không thể load embeddings đồng bộ. "
                        "Sử dụng create_with_embeddings() hoặc truyền kb_vectorstore trực tiếp."
                    )
                    self.kb_vectorstore = None
                else:
                    self.kb_vectorstore = loop.run_until_complete(
                        create_knowledge_base_vectorstore(
                            source_id=source_id,
                            document_id=document_id,
                        )
                    )
                    if self.kb_vectorstore:
                        logger.info("Đã load knowledge base vectorstore từ MongoDB")
                    else:
                        logger.warning("Không thể load knowledge base vectorstore từ MongoDB")
            except Exception as e:
                logger.warning(f"Không thể tự động load embeddings từ MongoDB: {e}")
                self.kb_vectorstore = None
        else:
            self.kb_vectorstore = kb_vectorstore
    
    @classmethod
    async def create_with_embeddings(
        cls,
        source_id: Optional[str] = None,
        document_id: Optional[str] = None,
        llm: Optional[ChatOpenAI] = None,
    ) -> "KnowledgeBaseRetriever":
        """
        Factory method để tạo KnowledgeBaseRetriever với embeddings từ MongoDB (async).
        
        Args:
            source_id: Source ID để filter (nếu None, lấy tất cả)
            document_id: Document ID để filter (nếu None, lấy tất cả)
            llm: LLM instance để dùng cho reranking
            
        Returns:
            KnowledgeBaseRetriever instance với vectorstore đã được load
        """
        vectorstore = await create_knowledge_base_vectorstore(
            source_id=source_id,
            document_id=document_id,
        )
        return cls(
            kb_vectorstore=vectorstore,
            llm=llm,
            source_id=source_id,
            document_id=document_id,
            auto_load_embeddings=False,
        )

    def get_kb_retriever(self) -> Optional[ContextualCompressionRetriever]:
        """
        Tạo compression retriever từ knowledge base vectorstore với reranking.
        
        Returns:
            ContextualCompressionRetriever hoặc None nếu không có vectorstore
        """
        retriever = (
            self.kb_vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs={"k": 5, "lambda_mult": 0.5}  # Lấy ít hơn cho knowledge base (5 vs 50)
            )
            if self.kb_vectorstore
            else None
        )

        if retriever is None:
            logger.warning("Knowledge base vectorstore is None, cannot create retriever")
            return None

        # Sử dụng LLMListwiseRerank để rerank kết quả
        compressor = LLMListwiseRerank.from_llm(llm=self.llm, top_n=3)  # Top 3 cho knowledge base

        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=retriever
        )

        return compression_retriever

