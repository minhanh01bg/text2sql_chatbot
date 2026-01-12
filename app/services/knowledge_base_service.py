"""
Service để xử lý knowledge base:
- Tạo embeddings cho chunks
- Lưu KnowledgeBaseDocument và KnowledgeBaseChunkEmbedding vào MongoDB
"""
import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

from app.core.database import get_database
from app.core.config import settings
from app.models.knowledge_base import KnowledgeBaseDocument, KnowledgeBaseChunkEmbedding

logger = logging.getLogger(__name__)


async def create_embeddings_for_chunks(
    chunks: List[Document],
    embedding_model_instance: Optional[OpenAIEmbeddings] = None,
    embedding_model_name: str = "text-embedding-3-large",
) -> List[KnowledgeBaseChunkEmbedding]:
    """
    Tạo embeddings cho list chunks.
    
    Args:
        chunks: List LangChain Document objects (đã có metadata đầy đủ)
        embedding_model_instance: OpenAIEmbeddings instance (nếu None, sẽ tạo mới)
        embedding_model_name: Tên embedding model
        
    Returns:
        List KnowledgeBaseChunkEmbedding objects
    """
    if not chunks:
        logger.warning("Empty chunks list provided for embedding")
        return []
    
    # Khởi tạo embedding model nếu chưa có
    if embedding_model_instance is None:
        embedding_model_instance = OpenAIEmbeddings(
            model=embedding_model_name,
            openai_api_key=settings.openai_api_key,
        )
    
    embeddings = []
    
    for idx, chunk_doc in enumerate(chunks):
        try:
            chunk_text = chunk_doc.page_content
            chunk_metadata = chunk_doc.metadata or {}
            
            # Lấy thông tin từ metadata
            document_id = chunk_metadata.get("document_id", "")
            source_id = chunk_metadata.get("source_id", "")
            chunk_index = chunk_metadata.get("chunk_index", idx)
            
            if not document_id or not source_id:
                logger.warning(
                    f"Chunk {idx} missing document_id or source_id, skipping"
                )
                continue
            
            # Tạo embedding vector
            try:
                if hasattr(embedding_model_instance, 'aembed_query'):
                    embedding_vector = await embedding_model_instance.aembed_query(chunk_text)
                else:
                    # Fallback to sync method in thread
                    embedding_vector = await asyncio.to_thread(
                        embedding_model_instance.embed_query,
                        chunk_text
                    )
            except Exception as e:
                logger.error(f"Error creating embedding for chunk {idx}: {e}")
                continue
            
            # Tạo KnowledgeBaseChunkEmbedding
            chunk_embedding = KnowledgeBaseChunkEmbedding(
                document_id=document_id,
                source_id=source_id,
                chunk_index=chunk_index,
                text=chunk_text,
                embedding_vector=embedding_vector,
                embedding_model=embedding_model_name,
                metadata=chunk_metadata,
            )
            
            embeddings.append(chunk_embedding)
            
        except Exception as e:
            logger.error(f"Error processing chunk {idx}: {e}", exc_info=True)
            continue
    
    logger.info(f"Created {len(embeddings)} embeddings from {len(chunks)} chunks")
    
    return embeddings


async def save_knowledge_base_document(
    document: KnowledgeBaseDocument,
) -> str:
    """
    Lưu KnowledgeBaseDocument vào MongoDB.
    
    Args:
        document: KnowledgeBaseDocument object
        
    Returns:
        ID của document đã được lưu (string)
    """
    db = get_database()
    if db is None:
        raise RuntimeError("MongoDB chưa được kết nối. Gọi connect_to_mongo() trước.")
    
    collection = db.knowledge_base_documents
    
    # Convert thành dict để lưu vào MongoDB
    doc_dict = document.model_dump(exclude={"id"})
    
    # Insert vào MongoDB
    result = await collection.insert_one(doc_dict)
    document_id = str(result.inserted_id)
    
    logger.info(
        f"Saved KnowledgeBaseDocument: {document_id} "
        f"(source_id: {document.source_id}, filename: {document.filename})"
    )
    
    return document_id


async def save_knowledge_base_chunk_embeddings(
    chunk_embeddings: List[KnowledgeBaseChunkEmbedding],
) -> List[str]:
    """
    Lưu list KnowledgeBaseChunkEmbedding vào MongoDB.
    
    Args:
        chunk_embeddings: List KnowledgeBaseChunkEmbedding objects
        
    Returns:
        List IDs của các embeddings đã được lưu
    """
    if not chunk_embeddings:
        logger.warning("Empty chunk_embeddings list provided")
        return []
    
    db = get_database()
    if db is None:
        raise RuntimeError("MongoDB chưa được kết nối. Gọi connect_to_mongo() trước.")
    
    collection = db.knowledge_base_embeddings
    
    # Convert thành list of dicts để bulk insert
    documents = []
    for emb in chunk_embeddings:
        doc_dict = emb.model_dump(exclude={"id"})
        documents.append(doc_dict)
    
    # Bulk insert vào MongoDB
    if documents:
        result = await collection.insert_many(documents)
        doc_ids = [str(id) for id in result.inserted_ids]
        
        logger.info(
            f"Saved {len(doc_ids)} KnowledgeBaseChunkEmbeddings "
            f"(document_id: {chunk_embeddings[0].document_id if chunk_embeddings else 'N/A'})"
        )
        
        return doc_ids
    
    return []


async def process_and_save_docx_file(
    file_content: bytes,
    filename: str,
    source_id: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    embedding_model_name: str = "text-embedding-3-large",
) -> Dict[str, Any]:
    """
    Xử lý file DOCX từ đầu đến cuối:
    1. Load DOCX và convert sang Markdown
    2. Split thành chunks với table awareness
    3. Tạo embeddings cho chunks
    4. Lưu KnowledgeBaseDocument và KnowledgeBaseChunkEmbedding vào MongoDB
    
    Args:
        file_content: Bytes content của file DOCX
        filename: Tên file
        source_id: Source ID (nếu None, sẽ tự generate từ filename)
        title: Tiêu đề document (optional)
        description: Mô tả document (optional)
        metadata: Metadata bổ sung (optional)
        embedding_model_name: Tên embedding model
        
    Returns:
        Dict chứa:
            - document_id: ID của KnowledgeBaseDocument đã lưu
            - source_id: Source ID đã dùng
            - chunk_count: Số chunks đã tạo
            - embedding_ids: List IDs của embeddings đã lưu
    """
    from app.core.knowledge_base_utils import (
        load_docx_from_bytes,
        split_documents_into_chunks,
        prepare_chunks_for_embedding,
    )
    import uuid
    
    # Generate source_id nếu chưa có
    if not source_id:
        source_id = str(uuid.uuid4())
    
    try:
        # Bước 1: Load DOCX và convert sang Markdown
        logger.info(f"Loading DOCX file: {filename}")
        documents = load_docx_from_bytes(file_content, filename)
        
        if not documents:
            raise ValueError(f"Không thể load nội dung từ file {filename}")
        
        # Bước 2: Split thành chunks với table awareness
        logger.info(f"Splitting {len(documents)} documents into chunks...")
        chunked_docs = split_documents_into_chunks(
            documents,
            metadata=metadata,
            use_markdown_splitting=True,
        )
        
        if not chunked_docs:
            raise ValueError(f"Không thể split documents thành chunks")
        
        # Bước 3: Tạo KnowledgeBaseDocument
        kb_document = KnowledgeBaseDocument(
            source_id=source_id,
            filename=filename,
            title=title,
            description=description,
            metadata=metadata or {},
        )
        
        # Bước 4: Lưu KnowledgeBaseDocument vào MongoDB
        document_id = await save_knowledge_base_document(kb_document)
        
        # Bước 5: Prepare chunks với document_id và source_id
        prepared_chunks = prepare_chunks_for_embedding(
            chunked_docs,
            document_id=document_id,
            source_id=source_id,
        )
        
        # Bước 6: Tạo embeddings cho chunks
        logger.info(f"Creating embeddings for {len(prepared_chunks)} chunks...")
        chunk_embeddings = await create_embeddings_for_chunks(
            prepared_chunks,
            embedding_model_name=embedding_model_name,
        )
        
        if not chunk_embeddings:
            raise ValueError("Không thể tạo embeddings cho chunks")
        
        # Bước 7: Lưu embeddings vào MongoDB
        embedding_ids = await save_knowledge_base_chunk_embeddings(chunk_embeddings)
        
        logger.info(
            f"Successfully processed DOCX file: {filename}\n"
            f"  - Document ID: {document_id}\n"
            f"  - Source ID: {source_id}\n"
            f"  - Chunks: {len(chunk_embeddings)}\n"
            f"  - Embeddings saved: {len(embedding_ids)}"
        )
        
        return {
            "document_id": document_id,
            "source_id": source_id,
            "chunk_count": len(chunk_embeddings),
            "embedding_ids": embedding_ids,
            "filename": filename,
        }
        
    except Exception as e:
        logger.error(f"Error processing DOCX file {filename}: {e}", exc_info=True)
        raise

