"""
Helper functions để lấy và format schema information từ MongoDB cho SQL generation.
"""
import logging
from typing import Optional, List, Dict, Any
from langchain_core.documents import Document

from app.core.database import get_database
from app.core.create_schema_embeddings import get_schema_from_mongodb
from app.models.database_schema import DatabaseSchema, TableInfo

logger = logging.getLogger(__name__)


def format_table_info_to_create_table(table_info: TableInfo, database_type: str = "postgres") -> str:
    """
    Format TableInfo thành CREATE TABLE statement.
    
    Args:
        table_info: TableInfo object từ MongoDB
        database_type: Loại database ("postgres" hoặc "mysql")
        
    Returns:
        CREATE TABLE statement string
    """
    # Tên table với schema
    if table_info.table_schema and table_info.table_schema != "public":
        full_table_name = f"{table_info.table_schema}.{table_info.table_name}"
    else:
        full_table_name = table_info.table_name
    
    lines = [f"CREATE TABLE {full_table_name} ("]
    
    # Format columns
    column_definitions = []
    for col in table_info.columns:
        col_parts = [f'"{col.name}"']
        
        # Data type với length/precision nếu có
        data_type = col.data_type
        if col.character_maximum_length:
            data_type = f"{data_type}({col.character_maximum_length})"
        elif col.numeric_precision and col.numeric_scale:
            data_type = f"{data_type}({col.numeric_precision},{col.numeric_scale})"
        elif col.numeric_precision:
            data_type = f"{data_type}({col.numeric_precision})"
        
        col_parts.append(data_type)
        
        # Constraints
        if col.is_primary_key:
            col_parts.append("PRIMARY KEY")
        if not col.is_nullable:
            col_parts.append("NOT NULL")
        if col.default_value:
            col_parts.append(f"DEFAULT {col.default_value}")
        
        column_definitions.append(" ".join(col_parts))
    
    lines.append(",\n  ".join(column_definitions))
    lines.append(");")
    
    # Foreign keys (nếu có)
    fk_columns = [col for col in table_info.columns if col.is_foreign_key and col.foreign_key_table]
    if fk_columns:
        lines.append("\n-- Foreign Keys:")
        for col in fk_columns:
            fk_table = col.foreign_key_table
            fk_col = col.foreign_key_column or "?"
            lines.append(f"-- {full_table_name}.{col.name} -> {fk_table}.{fk_col}")
    
    # Indexes (nếu có)
    if table_info.indexes:
        lines.append("\n-- Indexes:")
        for idx in table_info.indexes:
            idx_name = idx.get("name", "unnamed")
            idx_columns = ", ".join(idx.get("columns", []))
            is_unique = "UNIQUE " if idx.get("is_unique") else ""
            lines.append(f"-- {is_unique}{idx_name} on ({idx_columns})")
    
    # Row count (nếu có)
    if table_info.row_count is not None:
        lines.append(f"\n-- Row Count: {table_info.row_count:,}")
    
    return "\n".join(lines)


async def get_table_schemas_from_retrieved_docs(
    retrieved_docs: List[Document],
    schema_doc_id: Optional[str] = None
) -> str:
    """
    Lấy CREATE TABLE statements từ MongoDB dựa trên retrieved_docs.
    
    Args:
        retrieved_docs: Danh sách Document từ retriever
        schema_doc_id: ID của schema document (nếu None, sẽ lấy từ docs hoặc dùng mới nhất)
        
    Returns:
        String chứa các CREATE TABLE statements, mỗi statement cách nhau bởi \n\n
    """
    if not retrieved_docs:
        logger.warning("No retrieved docs provided")
        return ""
    
    # Lấy schema_doc_id từ docs nếu chưa có
    if not schema_doc_id:
        first_doc = retrieved_docs[0]
        if first_doc.metadata and "schema_doc_id" in first_doc.metadata:
            schema_doc_id = first_doc.metadata["schema_doc_id"]
    
    if not schema_doc_id:
        logger.warning("No schema_doc_id found in retrieved_docs, using latest schema")
    
    # Lấy DatabaseSchema từ MongoDB
    database_schema = await get_schema_from_mongodb(schema_doc_id)
    if not database_schema:
        logger.error(f"Could not load schema from MongoDB (schema_doc_id: {schema_doc_id})")
        return ""
    
    # Tạo dict để lookup table nhanh: (table_schema, table_name) -> TableInfo
    table_lookup: Dict[tuple, TableInfo] = {}
    for table in database_schema.tables:
        key = (table.table_schema, table.table_name)
        table_lookup[key] = table
    
    # Lấy table names từ retrieved_docs
    table_schemas = []
    seen_tables = set()
    
    for doc in retrieved_docs:
        if not doc.metadata:
            continue
        
        table_name = doc.metadata.get("table_name")
        table_schema_name = doc.metadata.get("table_schema", "public")
        
        if not table_name:
            continue
        
        # Tránh duplicate
        table_key = (table_schema_name, table_name)
        if table_key in seen_tables:
            continue
        seen_tables.add(table_key)
        
        # Lấy TableInfo từ lookup
        table_info = table_lookup.get(table_key)
        if table_info:
            create_table_stmt = format_table_info_to_create_table(
                table_info, 
                database_schema.database_type
            )
            table_schemas.append(create_table_stmt)
        else:
            logger.warning(
                f"Table not found in schema: {table_schema_name}.{table_name} "
                f"(schema_doc_id: {schema_doc_id})"
            )
    
    if not table_schemas:
        logger.warning("No table schemas found from retrieved_docs")
        return ""
    
    return "\n\n".join(table_schemas)

