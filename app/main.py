from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.core.sql_database import init_sql_connector, get_sql_connector
from app.api.routes import api_router
from app.graph.data_retriever import DataRetriever
from app.graph.knowledge_base_retriever import KnowledgeBaseRetriever
from app.graph import graph
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    # Kết nối MongoDB
    await connect_to_mongo()
    logger.info("✓ MongoDB connected successfully")
    
    # Kết nối PostgreSQL cho text2sql
    logger.info("=" * 60)
    logger.info("Đang kết nối đến PostgreSQL database...")
    try:
        # Khởi tạo connector với db_type="postgres" và lưu vào global instance
        sql_connector = init_sql_connector(db_type="postgres")
        if sql_connector is None:
            logger.warning("⚠ Không thể kết nối PostgreSQL: Không tìm thấy cấu hình trong environment variables")
            logger.warning("   Vui lòng kiểm tra các biến: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD")
        else:
            # Kiểm tra kết nối
            if sql_connector.test_connection():
                tables = sql_connector.get_tables()
                table_count = len(tables) if tables else 0
                logger.info("=" * 60)
                logger.info("✓ POSTGRESQL DATABASE CONNECTED SUCCESSFULLY!")
                logger.info(f"  - Host: {sql_connector.host}:{sql_connector.port}")
                logger.info(f"  - Database: {sql_connector.database}")
                logger.info(f"  - User: {sql_connector.user}")
                logger.info(f"  - Số bảng: {table_count}")
                if table_count > 0:
                    logger.info(f"  - Danh sách bảng: {', '.join(tables[:10])}{'...' if table_count > 10 else ''}")
                logger.info("=" * 60)
            else:
                logger.error("✗ PostgreSQL connection test failed")
    except Exception as e:
        logger.error("=" * 60)
        logger.error("✗ LỖI KẾT NỐI POSTGRESQL DATABASE!")
        logger.error(f"  - Error: {str(e)}")
        logger.error("=" * 60)
    
    # Load schema embeddings và khởi tạo DataRetriever
    logger.info("=" * 60)
    logger.info("Đang load schema embeddings từ MongoDB...")
    try:
        data_retriever = await DataRetriever.create_with_embeddings()
        if data_retriever and data_retriever.data_vectorstore:
            logger.info("✓ SCHEMA EMBEDDINGS LOADED SUCCESSFULLY!")
            # Cập nhật graph instance với data_retriever
            graph.data_retriever = data_retriever
            logger.info("  - DataRetriever đã được khởi tạo và gắn vào Graph")
        else:
            logger.warning("⚠ Không thể load schema embeddings từ MongoDB")
            logger.warning("   Có thể chưa có embeddings trong database. Chạy create_schema_embeddings script trước.")
    except Exception as e:
        logger.error("=" * 60)
        logger.error("✗ LỖI KHI LOAD SCHEMA EMBEDDINGS!")
        logger.error(f"  - Error: {str(e)}")
        logger.error("=" * 60)
    
    # Load knowledge base embeddings và khởi tạo KnowledgeBaseRetriever
    logger.info("=" * 60)
    logger.info("Đang load knowledge base embeddings từ MongoDB...")
    try:
        kb_retriever = await KnowledgeBaseRetriever.create_with_embeddings()
        if kb_retriever and kb_retriever.kb_vectorstore:
            logger.info("✓ KNOWLEDGE BASE EMBEDDINGS LOADED SUCCESSFULLY!")
            # Cập nhật graph instance với kb_retriever
            graph.kb_retriever = kb_retriever
        else:
            logger.warning("⚠ Không thể load knowledge base embeddings từ MongoDB")
    except Exception as e:
        logger.warning("=" * 60)
        logger.warning("⚠ LỖI KHI LOAD KNOWLEDGE BASE EMBEDDINGS!")
        logger.warning(f"  - Error: {str(e)}")
        logger.warning("   Graph vẫn hoạt động nhưng không có knowledge base cho out_of_scope")
        logger.warning("=" * 60)
    
    logger.info("Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown"""
    await close_mongo_connection()
    logger.info("Application shut down successfully")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "FastBase AI API",
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected"
    }

