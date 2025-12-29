from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    """Thông tin về một column trong bảng"""
    name: str
    data_type: str
    is_nullable: bool
    default_value: Optional[str] = None
    character_maximum_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_table: Optional[str] = None
    foreign_key_column: Optional[str] = None
    description: Optional[str] = None


class TableInfo(BaseModel):
    """Thông tin về một bảng trong database"""
    table_name: str
    table_schema: str
    columns: List[ColumnInfo] = []
    indexes: List[Dict[str, Any]] = []
    row_count: Optional[int] = None
    description: Optional[str] = None


class DatabaseSchema(BaseModel):
    """
    Model lưu toàn bộ schema information của một database.
    
    Collection: `database_schemas`
    - Một document = schema của một database tại một thời điểm
    - Có thể có nhiều documents cho cùng database (versioning theo timestamp)
    """
    
    id: Optional[str] = Field(None, alias="_id")
    database_name: str
    database_type: str  # "postgres" hoặc "mysql"
    host: str
    port: str
    tables: List[TableInfo] = []
    views: List[Dict[str, Any]] = []  # Views nếu có
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}  # Thông tin bổ sung

    class Config:
        populate_by_name = True


class TableEmbedding(BaseModel):
    """
    Model lưu embedding vector cho một table trong database schema.
    
    Collection: `database_schema_embeddings`
    - Một document = embedding của một table
    - Có thể có nhiều versions cho cùng table (khi schema thay đổi)
    """
    
    id: Optional[str] = Field(None, alias="_id")
    schema_doc_id: str  # Reference đến document trong database_schemas
    database_name: str
    database_type: str  # "postgres" hoặc "mysql"
    table_name: str
    table_schema: str
    embedding_text: str  # Text đã format để embedding
    embedding_vector: List[float]  # Vector embedding
    embedding_model: str = "text-embedding-3-small"  # Model đã dùng để tạo embedding
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Thông tin bổ sung
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

