from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field


class KnowledgeBaseDocument(BaseModel):
    """
    Model đại diện cho một tài liệu trong knowledge base (ví dụ: file DOCX người dùng upload).

    Mỗi document có thể được split thành nhiều chunks, mỗi chunk có embedding riêng.
    """

    # id: Optional[str] = Field(None, alias="_id")
    source_id: str  # ID logic để group (ví dụ: file_id hoặc business key)
    filename: str
    content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = {}

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class KnowledgeBaseChunkEmbedding(BaseModel):
    """
    Model lưu chunk text + embedding vector dùng cho RAG.

    Collection: `knowledge_base_embeddings`
    - Một document = một chunk (đoạn text) của một KnowledgeBaseDocument
    """

    # id: Optional[str] = Field(None, alias="_id")
    document_id: str  # Reference tới KnowledgeBaseDocument
    source_id: str  # Redundant để query nhanh theo source
    chunk_index: int
    text: str  # Nội dung chunk
    embedding_vector: List[float]
    embedding_model: str = "text-embedding-3-large"

    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


