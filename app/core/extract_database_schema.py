"""
Script để trích xuất toàn bộ schema information từ SQL database và lưu vào MongoDB.

Sử dụng:
    python -m app.core.extract_database_schema
    
Hoặc từ code:
    from app.core.extract_database_schema import extract_and_save_schema
    await extract_and_save_schema()
"""
import asyncio
import logging
from typing import Optional
from sqlalchemy import create_engine, text

from app.core.database import connect_to_mongo, get_database
from app.core.sql_database import SQLDatabaseConnector, create_sql_connector
from app.models.database_schema import DatabaseSchema, TableInfo, ColumnInfo
from app.core.config import settings

logger = logging.getLogger(__name__)


async def extract_postgres_schema(
    connector: SQLDatabaseConnector
) -> DatabaseSchema:
    """
    Trích xuất schema từ PostgreSQL database.
    
    Args:
        connector: SQLDatabaseConnector instance
        
    Returns:
        DatabaseSchema object chứa toàn bộ schema information
    """
    # Tạo SQLAlchemy engine để query information_schema
    engine = create_engine(connector.db_uri)
    
    with engine.connect() as connection:
        # Lấy danh sách tables (bao gồm schema)
        tables_query = text("""
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            AND table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name
        """)
        tables_result = connection.execute(tables_query)
        tables = [{"table_schema": row[0], "table_name": row[1], "table_type": row[2]} for row in tables_result]
        
        table_infos = []
        
        for table_row in tables:
            schema_name = table_row['table_schema']
            table_name = table_row['table_name']
            full_table_name = f"{schema_name}.{table_name}" if schema_name != 'public' else table_name
            
            # Lấy columns với chi tiết
            columns_query = text("""
                SELECT 
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    c.character_maximum_length,
                    c.numeric_precision,
                    c.numeric_scale,
                    col_description(pgc.oid, c.ordinal_position) as description
                FROM information_schema.columns c
                JOIN pg_class pgc ON pgc.relname = c.table_name
                JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace AND pgn.nspname = c.table_schema
                WHERE c.table_schema = :schema_name AND c.table_name = :table_name
                ORDER BY c.ordinal_position
            """)
            columns_result = connection.execute(
                columns_query,
                {"schema_name": schema_name, "table_name": table_name}
            )
            columns_data = [
                {
                    "column_name": row[0],
                    "data_type": row[1],
                    "is_nullable": row[2],
                    "column_default": row[3],
                    "character_maximum_length": row[4],
                    "numeric_precision": row[5],
                    "numeric_scale": row[6],
                    "description": row[7]
                }
                for row in columns_result
            ]
            
            # Lấy primary keys
            pk_query = text("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                JOIN pg_class pgc ON pgc.oid = i.indrelid
                JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace
                WHERE i.indisprimary = true
                AND pgn.nspname = :schema_name
                AND pgc.relname = :table_name
            """)
            pk_result = connection.execute(
                pk_query,
                {"schema_name": schema_name, "table_name": table_name}
            )
            primary_keys = {row[0] for row in pk_result}
            
            # Lấy foreign keys
            fk_query = text("""
                SELECT
                    kcu.column_name,
                    ccu.table_schema AS foreign_table_schema,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = :schema_name
                    AND tc.table_name = :table_name
            """)
            fk_result = connection.execute(
                fk_query,
                {"schema_name": schema_name, "table_name": table_name}
            )
            foreign_keys = {
                row[0]: {
                    "table": f"{row[1]}.{row[2]}" if row[1] != 'public' else row[2],
                    "column": row[3]
                }
                for row in fk_result
            }
            
            # Lấy indexes
            indexes_query = text("""
                SELECT
                    i.relname AS index_name,
                    a.attname AS column_name,
                    ix.indisunique AS is_unique
                FROM pg_index ix
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_class t ON t.oid = ix.indrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE n.nspname = :schema_name
                AND t.relname = :table_name
                AND NOT ix.indisprimary
            """)
            indexes_result = connection.execute(
                indexes_query,
                {"schema_name": schema_name, "table_name": table_name}
            )
            indexes_dict = {}
            for row in indexes_result:
                idx_name = row[0]
                if idx_name not in indexes_dict:
                    indexes_dict[idx_name] = {
                        "name": idx_name,
                        "columns": [],
                        "is_unique": row[2]
                    }
                indexes_dict[idx_name]["columns"].append(row[1])
            indexes = list(indexes_dict.values())
            
            # Lấy row count
            count_query = text(f'SELECT COUNT(*) as count FROM "{schema_name}"."{table_name}"')
            try:
                count_result = connection.execute(count_query)
                row_count = count_result.scalar()
            except Exception as e:
                logger.warning(f"Không thể lấy row count cho {full_table_name}: {e}")
                row_count = None
            
            # Tạo ColumnInfo objects
            column_infos = []
            for col in columns_data:
                col_name = col['column_name']
                fk_info = foreign_keys.get(col_name)
                
                column_info = ColumnInfo(
                    name=col_name,
                    data_type=col['data_type'],
                    is_nullable=col['is_nullable'] == 'YES',
                    default_value=col['column_default'],
                    character_maximum_length=col['character_maximum_length'],
                    numeric_precision=col['numeric_precision'],
                    numeric_scale=col['numeric_scale'],
                    is_primary_key=col_name in primary_keys,
                    is_foreign_key=fk_info is not None,
                    foreign_key_table=fk_info['table'] if fk_info else None,
                    foreign_key_column=fk_info['column'] if fk_info else None,
                    description=col['description']
                )
                column_infos.append(column_info)
            
            # Tạo TableInfo
            table_info = TableInfo(
                table_name=full_table_name,
                table_schema=schema_name,
                columns=column_infos,
                indexes=indexes,
                row_count=row_count
            )
            table_infos.append(table_info)
        
        # Lấy views
        views_query = text("""
            SELECT table_schema, table_name, view_definition
            FROM information_schema.views
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
        """)
        views_result = connection.execute(views_query)
        views = [
            {
                "schema": row[0],
                "name": f"{row[0]}.{row[1]}" if row[0] != 'public' else row[1],
                "definition": row[2]
            }
            for row in views_result
        ]
    
    # Tạo DatabaseSchema
    schema = DatabaseSchema(
        database_name=connector.database,
        database_type="postgres",
        host=connector.host,
        port=connector.port,
        tables=table_infos,
        views=views,
        metadata={
            "user": connector.user,
            "extracted_by": "extract_database_schema"
        }
    )
    
    return schema


async def extract_mysql_schema(
    connector: SQLDatabaseConnector
) -> DatabaseSchema:
    """
    Trích xuất schema từ MySQL database.
    
    Args:
        connector: SQLDatabaseConnector instance
        
    Returns:
        DatabaseSchema object chứa toàn bộ schema information
    """
    engine = create_engine(connector.db_uri)
    
    with engine.connect() as connection:
        # Lấy danh sách tables
        tables_query = text("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema = :db_name
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables_result = connection.execute(
            tables_query,
            {"db_name": connector.database}
        )
        tables = [{"table_schema": row[0], "table_name": row[1]} for row in tables_result]
        
        table_infos = []
        
        for table_row in tables:
            table_name = table_row["table_name"]
            
            # Lấy columns
            columns_query = text("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale,
                    column_comment as description
                FROM information_schema.columns
                WHERE table_schema = :db_name AND table_name = :table_name
                ORDER BY ordinal_position
            """)
            columns_result = connection.execute(
                columns_query,
                {"db_name": connector.database, "table_name": table_name}
            )
            columns_data = [
                {
                    "column_name": row[0],
                    "data_type": row[1],
                    "is_nullable": row[2],
                    "column_default": row[3],
                    "character_maximum_length": row[4],
                    "numeric_precision": row[5],
                    "numeric_scale": row[6],
                    "description": row[7]
                }
                for row in columns_result
            ]
            
            # Lấy primary keys
            pk_query = text("""
                SELECT column_name
                FROM information_schema.key_column_usage
                WHERE table_schema = :db_name
                AND table_name = :table_name
                AND constraint_name = 'PRIMARY'
            """)
            pk_result = connection.execute(
                pk_query,
                {"db_name": connector.database, "table_name": table_name}
            )
            primary_keys = {row[0] for row in pk_result}
            
            # Lấy foreign keys
            fk_query = text("""
                SELECT
                    column_name,
                    referenced_table_schema,
                    referenced_table_name,
                    referenced_column_name
                FROM information_schema.key_column_usage
                WHERE table_schema = :db_name
                AND table_name = :table_name
                AND referenced_table_name IS NOT NULL
            """)
            fk_result = connection.execute(
                fk_query,
                {"db_name": connector.database, "table_name": table_name}
            )
            foreign_keys = {
                row[0]: {
                    "table": row[2],
                    "column": row[3]
                }
                for row in fk_result
            }
            
            # Lấy indexes
            indexes_query = text("""
                SELECT
                    index_name,
                    column_name,
                    non_unique
                FROM information_schema.statistics
                WHERE table_schema = :db_name
                AND table_name = :table_name
                AND index_name != 'PRIMARY'
                ORDER BY index_name, seq_in_index
            """)
            indexes_result = connection.execute(
                indexes_query,
                {"db_name": connector.database, "table_name": table_name}
            )
            indexes_dict = {}
            for row in indexes_result:
                idx_name = row[0]
                if idx_name not in indexes_dict:
                    indexes_dict[idx_name] = {
                        "name": idx_name,
                        "columns": [],
                        "is_unique": row[2] == 0
                    }
                indexes_dict[idx_name]["columns"].append(row[1])
            indexes = list(indexes_dict.values())
            
            # Lấy row count
            count_query = text(f"SELECT COUNT(*) as count FROM `{table_name}`")
            try:
                count_result = connection.execute(count_query)
                row_count = count_result.scalar()
            except Exception as e:
                logger.warning(f"Không thể lấy row count cho {table_name}: {e}")
                row_count = None
            
            # Tạo ColumnInfo objects
            column_infos = []
            for col in columns_data:
                col_name = col['column_name']
                fk_info = foreign_keys.get(col_name)
                
                column_info = ColumnInfo(
                    name=col_name,
                    data_type=col['data_type'],
                    is_nullable=col['is_nullable'] == 'YES',
                    default_value=col['column_default'],
                    character_maximum_length=col['character_maximum_length'],
                    numeric_precision=col['numeric_precision'],
                    numeric_scale=col['numeric_scale'],
                    is_primary_key=col_name in primary_keys,
                    is_foreign_key=fk_info is not None,
                    foreign_key_table=fk_info['table'] if fk_info else None,
                    foreign_key_column=fk_info['column'] if fk_info else None,
                    description=col['description']
                )
                column_infos.append(column_info)
            
            # Tạo TableInfo
            table_info = TableInfo(
                table_name=table_name,
                table_schema=connector.database,
                columns=column_infos,
                indexes=indexes,
                row_count=row_count
            )
            table_infos.append(table_info)
        
        # Lấy views
        views_query = text("""
            SELECT table_name, view_definition
            FROM information_schema.views
            WHERE table_schema = :db_name
            ORDER BY table_name
        """)
        views_result = connection.execute(
            views_query,
            {"db_name": connector.database}
        )
        views = [
            {
                "schema": connector.database,
                "name": row[0],
                "definition": row[1]
            }
            for row in views_result
        ]
    
    # Tạo DatabaseSchema
    schema = DatabaseSchema(
        database_name=connector.database,
        database_type="mysql",
        host=connector.host,
        port=connector.port,
        tables=table_infos,
        views=views,
        metadata={
            "user": connector.user,
            "extracted_by": "extract_database_schema"
        }
    )
    
    return schema


async def save_schema_to_mongodb(schema: DatabaseSchema) -> str:
    """
    Lưu schema vào MongoDB.
    
    Args:
        schema: DatabaseSchema object
        
    Returns:
        ID của document đã lưu
    """
    db = get_database()
    if db is None:
        raise RuntimeError("MongoDB chưa được kết nối. Gọi connect_to_mongo() trước.")
    
    collection = db.database_schemas
    schema_dict = schema.model_dump(exclude={"id"})
    
    result = await collection.insert_one(schema_dict)
    return str(result.inserted_id)


async def extract_and_save_schema(
    db_type: Optional[str] = None,
    connector: Optional[SQLDatabaseConnector] = None
) -> str:
    """
    Trích xuất schema từ SQL database và lưu vào MongoDB.
    
    Args:
        db_type: Loại database ("postgres" hoặc "mysql"). Nếu None, tự động detect.
        connector: SQLDatabaseConnector instance. Nếu None, tạo mới từ env.
        
    Returns:
        ID của document đã lưu vào MongoDB
    """
    # Kết nối MongoDB nếu chưa kết nối
    try:
        from app.core.database import mongodb
        if mongodb.database is None:
            await connect_to_mongo()
    except Exception:
        await connect_to_mongo()
    
    # Tạo connector nếu chưa có
    if connector is None:
        connector = create_sql_connector(db_type=db_type)
        if connector is None:
            raise ValueError("Không thể tạo database connector. Kiểm tra environment variables.")
    
    logger.info(f"Bắt đầu trích xuất schema từ {connector.db_type} database: {connector.host}:{connector.port}/{connector.database}")
    
    # Trích xuất schema theo loại database
    if connector.db_type == "postgres":
        schema = await extract_postgres_schema(connector)
    elif connector.db_type == "mysql":
        schema = await extract_mysql_schema(connector)
    else:
        raise ValueError(f"Database type '{connector.db_type}' không được hỗ trợ")
    
    logger.info(f"Đã trích xuất {len(schema.tables)} bảng, {len(schema.views)} views")
    
    # Lưu vào MongoDB
    doc_id = await save_schema_to_mongodb(schema)
    
    logger.info(f"Đã lưu schema vào MongoDB với ID: {doc_id}")
    
    return doc_id


async def main():
    """Entry point để chạy script từ command line."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        doc_id = await extract_and_save_schema()
        print(f"✓ Đã trích xuất và lưu schema thành công. Document ID: {doc_id}")
    except Exception as e:
        logger.error(f"Lỗi khi trích xuất schema: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())

