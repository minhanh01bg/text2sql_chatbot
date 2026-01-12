"""
Helper functions để load knowledge base embeddings từ MongoDB và tạo vectorstore.
"""
import logging
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.core.database import get_database
from app.models.knowledge_base import KnowledgeBaseChunkEmbedding
from app.core.config import settings

logger = logging.getLogger(__name__)


async def load_knowledge_base_embeddings_from_mongodb(
    source_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> List[KnowledgeBaseChunkEmbedding]:
    """
    Load knowledge base embeddings từ MongoDB.
    
    Args:
        source_id: Source ID để filter (nếu None, lấy tất cả)
        document_id: Document ID để filter (nếu None, lấy tất cả)
        
    Returns:
        List of KnowledgeBaseChunkEmbedding objects
    """
    db = get_database()
    if db is None:
        raise RuntimeError("MongoDB chưa được kết nối. Gọi connect_to_mongo() trước.")
    
    collection = db.knowledge_base_embeddings
    
    # Build query filter
    query_filter = {}
    if source_id:
        query_filter["source_id"] = source_id
    if document_id:
        query_filter["document_id"] = document_id
    
    # Load embeddings từ MongoDB
    cursor = collection.find(query_filter).sort("chunk_index", 1)  # Sort by chunk_index
    
    embeddings = []
    async for doc in cursor:
        # Convert ObjectId to string
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        # Convert datetime fields
        for field in ["created_at", "updated_at"]:
            if field in doc and not isinstance(doc[field], datetime):
                try:
                    doc[field] = datetime.fromisoformat(str(doc[field]).replace('Z', '+00:00'))
                except:
                    pass
        
        try:
            embeddings.append(KnowledgeBaseChunkEmbedding(**doc))
        except Exception as e:
            logger.warning(f"Error parsing embedding document: {e}")
            continue
    
    return embeddings


async def create_knowledge_base_vectorstore(
    source_id: Optional[str] = None,
    document_id: Optional[str] = None,
    embedding_model: Optional[OpenAIEmbeddings] = None,
) -> Optional[FAISS]:
    """
    Tạo FAISS vectorstore từ knowledge base embeddings đã lưu trong MongoDB.
    
    Args:
        source_id: Source ID để filter (nếu None, lấy tất cả)
        document_id: Document ID để filter (nếu None, lấy tất cả)
        embedding_model: OpenAIEmbeddings instance (cần để FAISS có thể embed queries mới)
        
    Returns:
        FAISS vectorstore hoặc None nếu không tìm thấy embeddings
    """
    # Load embeddings từ MongoDB
    embeddings_list = await load_knowledge_base_embeddings_from_mongodb(
        source_id=source_id,
        document_id=document_id,
    )
    
    if not embeddings_list:
        logger.warning("Không tìm thấy knowledge base embeddings trong MongoDB")
        return None
    
    logger.info(f"Đã load {len(embeddings_list)} knowledge base embeddings từ MongoDB")
    
    # Tạo Documents và metadata
    documents = []
    texts = []
    metadatas = []
    embeddings_vectors = []
    
    for emb in embeddings_list:
        # Tạo Document với text từ chunk
        doc_text = emb.text
        texts.append(doc_text)
        embeddings_vectors.append(emb.embedding_vector)
        
        # Tạo metadata
        metadata = {
            "document_id": emb.document_id,
            "source_id": emb.source_id,
            "chunk_index": emb.chunk_index,
            "embedding_id": str(emb.id) if emb.id else None,
            "embedding_model": emb.embedding_model,
        }
        # Merge với metadata từ embedding
        if emb.metadata:
            metadata.update(emb.metadata)
        metadatas.append(metadata)
        
        documents.append(Document(page_content=doc_text, metadata=metadata))
    
    # Tạo embedding model nếu chưa có
    if embedding_model is None:
        embedding_model = OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=settings.openai_api_key
        )
    
    # Tạo FAISS vectorstore từ embeddings đã có
    # Sử dụng custom Embeddings class để dùng precomputed embeddings
    
    class CustomEmbeddings(Embeddings):
        """Custom embeddings class sử dụng precomputed embeddings cho documents."""
        
        def __init__(self, precomputed_embeddings: List[List[float]], query_embedding_model):
            super().__init__()
            self.precomputed_embeddings = precomputed_embeddings
            self.query_embedding_model = query_embedding_model
        
        def embed_query(self, text: str) -> List[float]:
            """Embed query text (sử dụng embedding model thực tế)."""
            return self.query_embedding_model.embed_query(text)
        
        async def aembed_query(self, text: str) -> List[float]:
            """Async embed query text."""
            if hasattr(self.query_embedding_model, 'aembed_query'):
                return await self.query_embedding_model.aembed_query(text)
            else:
                return self.query_embedding_model.embed_query(text)
        
        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            """Return precomputed embeddings (không tính lại)."""
            return self.precomputed_embeddings
        
        async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
            """Async embed documents (return precomputed embeddings)."""
            return self.precomputed_embeddings
    
    # Tạo custom embeddings
    custom_emb = CustomEmbeddings(embeddings_vectors, embedding_model)
    
    # Tạo FAISS vectorstore với custom embeddings
    try:
        vectorstore = FAISS.from_documents(
            documents=documents,
            embedding=custom_emb
        )
        
        logger.info(f"Đã tạo FAISS vectorstore với {len(documents)} knowledge base documents")
        return vectorstore
        
    except Exception as e:
        logger.error(f"Lỗi khi tạo vectorstore: {e}", exc_info=True)
        # Fallback: tạo vectorstore từ texts và tính lại embeddings
        logger.warning("Fallback: tạo vectorstore bằng cách tính lại embeddings")
        vectorstore = FAISS.from_documents(
            documents=documents,
            embedding=embedding_model
        )
        return vectorstore

