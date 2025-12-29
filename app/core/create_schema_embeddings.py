"""
Script để tạo embedding vectors cho database schema tables và lưu vào MongoDB.

Sử dụng:
    python -m app.core.create_schema_embeddings
    
Hoặc từ code:
    from app.core.create_schema_embeddings import create_and_save_embeddings
    result = await create_and_save_embeddings(schema_doc_id="...")
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

from langchain_openai import OpenAIEmbeddings

from app.core.database import connect_to_mongo, get_database
from app.models.database_schema import DatabaseSchema, TableInfo, ColumnInfo, TableEmbedding
from app.core.config import settings

logger = logging.getLogger(__name__)


def format_table_embedding_text(table: TableInfo, database_name: str) -> str:
    """
    Format text representation của một table để embedding.
    
    Args:
        table: TableInfo object
        database_name: Tên database
        
    Returns:
        Formatted text string
    """
    # Tên table với schema
    full_table_name = f"{table.table_schema}.{table.table_name}" if table.table_schema != "public" else table.table_name
    lines = [f"Table: {full_table_name}"]
    
    # Description nếu có
    if table.description:
        lines.append(f"Description: {table.description}")
    
    lines.append("\nColumns:")
    
    # Format columns
    for col in table.columns:
        col_parts = [f"- {col.name} ({col.data_type})"]
        
        # Constraints và relationships
        constraints = []
        if col.is_primary_key:
            constraints.append("Primary Key")
        if col.is_foreign_key and col.foreign_key_table:
            fk_ref = col.foreign_key_column if col.foreign_key_column else "?"
            constraints.append(f"Foreign Key to {col.foreign_key_table}.{fk_ref}")
        if not col.is_nullable:
            constraints.append("NOT NULL")
        if col.default_value:
            constraints.append(f"Default: {col.default_value}")
        
        if constraints:
            col_parts.append(f" [{', '.join(constraints)}]")
        
        # Description
        if col.description:
            col_parts.append(f" - {col.description}")
        
        lines.append("".join(col_parts))
    
    # Primary keys summary
    pk_columns = [col.name for col in table.columns if col.is_primary_key]
    if pk_columns:
        lines.append(f"\nPrimary Keys: {', '.join(pk_columns)}")
    
    # Foreign keys summary
    fk_info = []
    for col in table.columns:
        if col.is_foreign_key and col.foreign_key_table:
            fk_ref = col.foreign_key_column if col.foreign_key_column else "?"
            fk_info.append(f"{col.name} -> {col.foreign_key_table}.{fk_ref}")
    if fk_info:
        lines.append(f"Foreign Keys: {'; '.join(fk_info)}")
    
    # Indexes
    if table.indexes:
        index_info = []
        for idx in table.indexes:
            idx_name = idx.get("name", "unnamed")
            idx_columns = ", ".join(idx.get("columns", []))
            is_unique = "UNIQUE " if idx.get("is_unique") else ""
            index_info.append(f"{is_unique}{idx_name} on ({idx_columns})")
        if index_info:
            lines.append(f"Indexes: {'; '.join(index_info)}")
    
    # Row count
    if table.row_count is not None:
        lines.append(f"Row Count: {table.row_count:,}")
    
    return "\n".join(lines)


async def get_schema_from_mongodb(schema_doc_id: Optional[str] = None) -> Optional[DatabaseSchema]:
    """
    Lấy schema document từ MongoDB.
    
    Args:
        schema_doc_id: ID của schema document. Nếu None, lấy schema mới nhất.
        
    Returns:
        DatabaseSchema object hoặc None nếu không tìm thấy
    """
    db = get_database()
    if db is None:
        raise RuntimeError("MongoDB chưa được kết nối. Gọi connect_to_mongo() trước.")
    
    collection = db.database_schemas
    
    if schema_doc_id:
        # Lấy schema theo ID
        doc = await collection.find_one({"_id": ObjectId(schema_doc_id)})
    else:
        # Lấy schema mới nhất
        doc = await collection.find_one(sort=[("extracted_at", -1)])
    
    if not doc:
        logger.warning(f"Không tìm thấy schema document" + (f" với ID {schema_doc_id}" if schema_doc_id else ""))
        return None
    
    # Convert ObjectId to string cho _id
    doc["_id"] = str(doc["_id"])
    
    # Convert datetime fields
    if "extracted_at" in doc and isinstance(doc["extracted_at"], datetime):
        pass  # Already datetime
    elif "extracted_at" in doc:
        doc["extracted_at"] = datetime.fromisoformat(str(doc["extracted_at"]).replace('Z', '+00:00'))
    
    return DatabaseSchema(**doc)


async def create_embeddings_for_table(
    table: TableInfo,
    schema_doc_id: str,
    database_name: str,
    database_type: str,
    embedding_model_instance: OpenAIEmbeddings
) -> TableEmbedding:
    """
    Tạo embedding cho một table.
    
    Args:
        table: TableInfo object
        schema_doc_id: ID của schema document
        database_name: Tên database
        database_type: Loại database
        embedding_model_instance: OpenAIEmbeddings instance
        
    Returns:
        TableEmbedding object
    """
    # Format text
    embedding_text = format_table_embedding_text(table, database_name)
    
    # Tạo embedding vector (OpenAIEmbeddings.embed_query là sync, cần wrap trong thread)
    try:
        # Thử dùng async method nếu có
        if hasattr(embedding_model_instance, 'aembed_query'):
            embedding_vector = await embedding_model_instance.aembed_query(embedding_text)
        else:
            # Fallback to sync method in thread
            embedding_vector = await asyncio.to_thread(
                embedding_model_instance.embed_query,
                embedding_text
            )
    except Exception as e:
        logger.error(f"Lỗi khi tạo embedding: {e}")
        raise
    
    # Prepare metadata
    pk_columns = [col.name for col in table.columns if col.is_primary_key]
    fk_list = [
        {
            "column": col.name,
            "foreign_table": col.foreign_key_table,
            "foreign_column": col.foreign_key_column
        }
        for col in table.columns
        if col.is_foreign_key and col.foreign_key_table
    ]
    
    metadata = {
        "column_count": len(table.columns),
        "row_count": table.row_count,
        "has_foreign_keys": len(fk_list) > 0,
        "primary_keys": pk_columns,
        "foreign_keys": fk_list,
        "index_count": len(table.indexes),
    }
    
    # Tạo TableEmbedding
    table_embedding = TableEmbedding(
        schema_doc_id=schema_doc_id,
        database_name=database_name,
        database_type=database_type,
        table_name=table.table_name,
        table_schema=table.table_schema,
        embedding_text=embedding_text,
        embedding_vector=embedding_vector,
        embedding_model=embedding_model_instance.model,
        metadata=metadata,
    )
    
    return table_embedding


async def save_embeddings_to_mongodb(embeddings: List[TableEmbedding]) -> List[str]:
    """
    Lưu list embeddings vào MongoDB.
    
    Args:
        embeddings: List of TableEmbedding objects
        
    Returns:
        List of document IDs đã lưu
    """
    db = get_database()
    if db is None:
        raise RuntimeError("MongoDB chưa được kết nối. Gọi connect_to_mongo() trước.")
    
    collection = db.database_schema_embeddings
    
    # Convert to dict và exclude id
    documents = [emb.model_dump(exclude={"id"}) for emb in embeddings]
    
    # Insert many
    result = await collection.insert_many(documents)
    
    return [str(id) for id in result.inserted_ids]


async def create_and_save_embeddings(
    schema_doc_id: Optional[str] = None,
    embedding_model_name: str = "text-embedding-3-large"
) -> Dict[str, Any]:
    """
    Tạo embeddings cho toàn bộ tables trong schema và lưu vào MongoDB.
    
    Args:
        schema_doc_id: ID của schema document. Nếu None, lấy schema mới nhất.
        embedding_model_name: Tên embedding model (default: "text-embedding-3-large")
        
    Returns:
        Dict chứa thông tin kết quả:
        {
            "schema_doc_id": str,
            "tables_processed": int,
            "embedding_doc_ids": List[str],
            "errors": List[str]
        }
    """
    # Kết nối MongoDB nếu chưa kết nối
    try:
        from app.core.database import mongodb
        if mongodb.database is None:
            await connect_to_mongo()
    except Exception:
        await connect_to_mongo()
    
    # Lấy schema từ MongoDB
    schema = await get_schema_from_mongodb(schema_doc_id)
    if schema is None:
        raise ValueError(f"Không tìm thấy schema document" + (f" với ID {schema_doc_id}" if schema_doc_id else ""))
    
    schema_doc_id = schema.id
    if not schema_doc_id:
        raise ValueError("Schema document không có ID")
    
    logger.info(f"Bắt đầu tạo embeddings cho schema {schema_doc_id}")
    logger.info(f"Database: {schema.database_name} ({schema.database_type})")
    logger.info(f"Số bảng: {len(schema.tables)}")
    
    # Khởi tạo embedding model
    embedding_model = OpenAIEmbeddings(
        model=embedding_model_name,
        openai_api_key=settings.openai_api_key
    )
    
    # Tạo embeddings cho từng table
    embeddings = []
    errors = []
    
    for idx, table in enumerate(schema.tables, 1):
        try:
            logger.info(f"Đang xử lý table {idx}/{len(schema.tables)}: {table.table_name}")
            embedding = await create_embeddings_for_table(
                table=table,
                schema_doc_id=schema_doc_id,
                database_name=schema.database_name,
                database_type=schema.database_type,
                embedding_model_instance=embedding_model
            )
            embeddings.append(embedding)
        except Exception as e:
            error_msg = f"Lỗi khi tạo embedding cho table {table.table_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
    
    # Lưu vào MongoDB
    if embeddings:
        doc_ids = await save_embeddings_to_mongodb(embeddings)
        logger.info(f"Đã lưu {len(doc_ids)} embeddings vào MongoDB")
    else:
        doc_ids = []
        logger.warning("Không có embedding nào được tạo")
    
    result = {
        "schema_doc_id": schema_doc_id,
        "tables_processed": len(embeddings),
        "total_tables": len(schema.tables),
        "embedding_doc_ids": doc_ids,
        "errors": errors,
        "embedding_model": embedding_model_name,
    }
    
    return result


async def main():
    """Entry point để chạy script từ command line."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        result = await create_and_save_embeddings()
        print(f"✓ Đã tạo và lưu embeddings thành công!")
        print(f"  Schema ID: {result['schema_doc_id']}")
        print(f"  Tables processed: {result['tables_processed']}/{result['total_tables']}")
        print(f"  Embedding documents: {len(result['embedding_doc_ids'])}")
        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")
            for error in result['errors']:
                print(f"    - {error}")
    except Exception as e:
        logger.error(f"Lỗi khi tạo embeddings: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())

