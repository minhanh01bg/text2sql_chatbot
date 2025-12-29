"""
Helper functions để load schema embeddings từ MongoDB và tạo vectorstore.
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
from app.models.database_schema import TableEmbedding
from app.core.config import settings

logger = logging.getLogger(__name__)


async def load_embeddings_from_mongodb(schema_doc_id: Optional[str] = None) -> List[TableEmbedding]:
    """
    Load embeddings từ MongoDB.
    
    Args:
        schema_doc_id: ID của schema document. Nếu None, lấy embeddings mới nhất.
        
    Returns:
        List of TableEmbedding objects
    """
    db = get_database()
    if db is None:
        raise RuntimeError("MongoDB chưa được kết nối. Gọi connect_to_mongo() trước.")
    
    collection = db.database_schema_embeddings
    
    if schema_doc_id:
        # Lấy embeddings theo schema_doc_id
        cursor = collection.find({"schema_doc_id": schema_doc_id})
    else:
        # Lấy embeddings mới nhất (theo created_at của schema)
        # First, get latest schema_doc_id
        schema_collection = db.database_schemas
        latest_schema = await schema_collection.find_one(sort=[("extracted_at", -1)])
        if not latest_schema:
            logger.warning("Không tìm thấy schema document")
            return []
        schema_doc_id = str(latest_schema["_id"])
        cursor = collection.find({"schema_doc_id": schema_doc_id})
    
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
        embeddings.append(TableEmbedding(**doc))
    
    return embeddings


async def create_vectorstore_from_embeddings(
    schema_doc_id: Optional[str] = None,
    embedding_model: Optional[OpenAIEmbeddings] = None
) -> Optional[FAISS]:
    """
    Tạo FAISS vectorstore từ embeddings đã lưu trong MongoDB.
    
    Args:
        schema_doc_id: ID của schema document. Nếu None, lấy embeddings mới nhất.
        embedding_model: OpenAIEmbeddings instance (cần để FAISS có thể embed queries mới)
        
    Returns:
        FAISS vectorstore hoặc None nếu không tìm thấy embeddings
    """
    # Load embeddings từ MongoDB
    embeddings_list = await load_embeddings_from_mongodb(schema_doc_id)
    
    if not embeddings_list:
        logger.warning("Không tìm thấy embeddings trong MongoDB")
        return None
    
    logger.info(f"Đã load {len(embeddings_list)} embeddings từ MongoDB")
    
    # Tạo Documents và metadata
    documents = []
    texts = []
    metadatas = []
    embeddings_vectors = []
    
    for emb in embeddings_list:
        # Tạo Document với embedding_text
        doc_text = emb.embedding_text
        texts.append(doc_text)
        embeddings_vectors.append(emb.embedding_vector)
        
        # Tạo metadata
        metadata = {
            "schema_doc_id": emb.schema_doc_id,
            "database_name": emb.database_name,
            "database_type": emb.database_type,
            "table_name": emb.table_name,
            "table_schema": emb.table_schema,
            "embedding_id": str(emb.id) if emb.id else None,
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
    # FAISS cần embedding function, nhưng ta muốn dùng precomputed embeddings
    # Giải pháp: tạo custom Embeddings class trả về precomputed embeddings cho documents
    # nhưng vẫn dùng embedding_model để embed queries mới
    
    class CustomEmbeddings(Embeddings):
        """Custom embeddings class sử dụng precomputed embeddings cho documents."""
        
        def __init__(self, precomputed_embeddings: List[List[float]], query_embedding_model):
            """
            Args:
                precomputed_embeddings: List of precomputed embedding vectors
                query_embedding_model: Embedding model để embed queries mới
            """
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
                # Fallback to sync method
                return self.query_embedding_model.embed_query(text)
        
        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            """Return precomputed embeddings (không tính lại)."""
            # Return precomputed embeddings theo thứ tự texts
            # Giả định texts có cùng thứ tự với precomputed_embeddings
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
        
        # Replace embedding attribute với embedding_model để FAISS có thể query
        # FAISS sẽ dùng custom_emb.embed_documents khi tạo index (sử dụng precomputed)
        # và dùng custom_emb.embed_query khi query (sử dụng embedding_model)
        
        logger.info(f"Đã tạo FAISS vectorstore với {len(documents)} documents")
        return vectorstore
        
    except Exception as e:
        logger.error(f"Lỗi khi tạo vectorstore: {e}", exc_info=True)
        # Fallback: tạo vectorstore từ texts và tính lại embeddings (chậm hơn nhưng chắc chắn hoạt động)
        logger.warning("Fallback: tạo vectorstore bằng cách tính lại embeddings với embedding_model")
        vectorstore = FAISS.from_documents(
            documents=documents,
            embedding=embedding_model
        )
        return vectorstore

