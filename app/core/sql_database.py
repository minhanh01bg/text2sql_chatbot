"""
Module kết nối và truy vấn SQL database cho chatbot text2sql
Hỗ trợ PostgreSQL và MySQL
"""
import os
import logging
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote
from dotenv import load_dotenv

from sqlalchemy import text as sa_text
from langchain_community.utilities import SQLDatabase
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class SQLDatabaseConnector:
    """
    Class để kết nối và truy vấn SQL database
    Hỗ trợ PostgreSQL và MySQL
    """
    
    def __init__(
        self,
        db_type: str = "postgres",
        host: Optional[str] = None,
        port: Optional[str] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Khởi tạo kết nối database
        
        Parameters
        ----------
        db_type : str
            Loại database: "postgres" hoặc "mysql"
        host : Optional[str]
            Host của database (mặc định từ env)
        port : Optional[str]
            Port của database (mặc định từ env)
        database : Optional[str]
            Tên database (mặc định từ env)
        user : Optional[str]
            Username (mặc định từ env)
        password : Optional[str]
            Password (mặc định từ env)
        """
        self.db_type = db_type.lower()
        
        # Lấy thông tin từ parameters hoặc environment variables
        if db_type.lower() == "postgres":
            self.host = host or settings.postgres_host or os.getenv("POSTGRES_HOST")
            self.port = port or settings.postgres_port or os.getenv("POSTGRES_PORT", "5432")
            self.database = database or settings.postgres_db or os.getenv("POSTGRES_DB")
            self.user = user or settings.postgres_user or os.getenv("POSTGRES_USER")
            self.password = password or settings.postgres_password or os.getenv("POSTGRES_PASSWORD")
        elif db_type.lower() == "mysql":
            self.host = host or settings.mysql_host or os.getenv("MYSQL_HOST")
            self.port = port or settings.mysql_port or os.getenv("MYSQL_PORT", "3306")
            self.database = database or settings.mysql_database or os.getenv("MYSQL_DATABASE")
            self.user = user or settings.mysql_user or os.getenv("MYSQL_USER")
            self.password = password or settings.mysql_password or os.getenv("MYSQL_PASSWORD")
        else:
            raise ValueError(f"Database type '{db_type}' không được hỗ trợ. Chỉ hỗ trợ 'postgres' hoặc 'mysql'")
        
        # Validate required fields
        if not all([self.host, self.database, self.user, self.password]):
            missing = []
            if not self.host:
                missing.append("host")
            if not self.database:
                missing.append("database")
            if not self.user:
                missing.append("user")
            if not self.password:
                missing.append("password")
            raise ValueError(
                f"Thiếu thông tin kết nối database: {', '.join(missing)}. "
                f"Vui lòng cung cấp qua parameters hoặc environment variables."
            )
        
        # Tạo connection URI
        self.db_uri = self._build_connection_uri()
        
        # Kết nối database
        try:
            self.db = SQLDatabase.from_uri(database_uri=self.db_uri)
            self.sql_tool = QuerySQLDatabaseTool(db=self.db)
            logger.info(f"Đã kết nối thành công đến {self.db_type} database: {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"Lỗi kết nối database: {e}")
            raise
    
    def _build_connection_uri(self) -> str:
        """Xây dựng connection URI từ thông tin kết nối"""
        # Encode password để xử lý các ký tự đặc biệt
        encoded_password = quote(str(self.password))
        
        if self.db_type == "postgres":
            return (
                f"postgresql://{self.user}:{encoded_password}@"
                f"{self.host}:{self.port}/{self.database}"
            )
        elif self.db_type == "mysql":
            return (
                f"mysql+pymysql://{self.user}:{encoded_password}@"
                f"{self.host}:{self.port}/{self.database}"
            )
        else:
            raise ValueError(f"Database type '{self.db_type}' không được hỗ trợ")
    
    def execute_query(self, query: str) -> Dict[str, Any]:
        """
        Thực thi câu SQL query và trả về kết quả dạng bảng có cấu trúc.

        Thay vì dùng SQLDatabase.run (trả về chuỗi đã format sẵn),
        hàm này truy vấn trực tiếp qua SQLAlchemy engine để lấy:
        - columns: danh sách tên cột
        - rows: list[dict], mỗi dict là một hàng {col: value}

        Parameters
        ----------
        query : str
            Câu SQL query cần thực thi

        Returns
        -------
        Dict[str, Any]
            {
                "columns": list[str],
                "rows": list[dict]
            }
            Kết quả dạng bảng, thuận tiện cho frontend visualize.
        """
        try:
            logger.debug(f"Thực thi query (structured): {query[:100]}...")
            # Truy vấn trực tiếp qua SQLAlchemy engine bên trong SQLDatabase
            with self.db._engine.connect() as conn:  # type: ignore[attr-defined]
                result = conn.execute(sa_text(query))
                rows_raw = result.fetchall()
                columns = list(result.keys())

            rows: List[Dict[str, Any]] = [
                {col: value for col, value in zip(columns, row)}
                for row in rows_raw
            ]

            return {"columns": columns, "rows": rows}
        except Exception as e:
            logger.error(f"Lỗi khi thực thi query: {e}")
            raise
    
    def execute_query_safe(self, query: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        """
        Thực thi câu SQL query an toàn, trả về tuple (success, result, error)
        
        Parameters
        ----------
        query : str
            Câu SQL query cần thực thi
        
        Returns
        -------
        Tuple[bool, Optional[Any], Optional[str]]
            (success, result, error_message)
        """
        try:
            result = self.execute_query(query)
            return True, result, None
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Lỗi khi thực thi query: {error_msg}")
            return False, None, error_msg
    
    def get_tables(self) -> List[str]:
        """
        Lấy danh sách tất cả các bảng trong database
        
        Returns
        -------
        List[str]
            Danh sách tên các bảng
        """
        try:
            tables = self.db.get_usable_table_names()
            return tables
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách bảng: {e}")
            raise
    
    def get_table_schema(self, table_name: str) -> str:
        """
        Lấy schema của một bảng cụ thể
        
        Parameters
        ----------
        table_name : str
            Tên bảng
        
        Returns
        -------
        str
            Schema của bảng (DDL)
        """
        try:
            schema = self.db.get_table_info_no_throw([table_name])
            return schema
        except Exception as e:
            logger.error(f"Lỗi khi lấy schema của bảng {table_name}: {e}")
            raise
    
    def get_all_schemas(self, table_names: Optional[List[str]] = None) -> str:
        """
        Lấy schema của tất cả các bảng hoặc các bảng được chỉ định
        
        Parameters
        ----------
        table_names : Optional[List[str]]
            Danh sách tên bảng (None để lấy tất cả)
        
        Returns
        -------
        str
            Schema của các bảng
        """
        try:
            if table_names is None:
                table_names = self.get_tables()
            schema = self.db.get_table_info_no_throw(table_names)
            return schema
        except Exception as e:
            logger.error(f"Lỗi khi lấy schema: {e}")
            raise
    
    def get_database_instance(self) -> SQLDatabase:
        """
        Lấy instance SQLDatabase của langchain
        
        Returns
        -------
        SQLDatabase
            Instance SQLDatabase
        """
        return self.db
    
    def get_query_tool(self) -> QuerySQLDatabaseTool:
        """
        Lấy query tool của langchain
        
        Returns
        -------
        QuerySQLDatabaseTool
            Query tool instance
        """
        return self.sql_tool
    
    def test_connection(self) -> bool:
        """
        Kiểm tra kết nối database
        
        Returns
        -------
        bool
            True nếu kết nối thành công
        """
        try:
            # Thử lấy danh sách bảng để kiểm tra kết nối
            self.get_tables()
            return True
        except Exception as e:
            logger.error(f"Kết nối database thất bại: {e}")
            return False


# Factory function để tạo connector từ environment variables
def create_sql_connector(
    db_type: Optional[str] = None,
    **kwargs
) -> Optional[SQLDatabaseConnector]:
    """
    Tạo SQLDatabaseConnector từ environment variables
    
    Parameters
    ----------
    db_type : Optional[str]
        Loại database: "postgres" hoặc "mysql" (mặc định: tự động detect)
    **kwargs
        Các tham số override cho connection
    
    Returns
    -------
    Optional[SQLDatabaseConnector]
        SQLDatabaseConnector instance hoặc None nếu không có cấu hình
    """
    # Auto-detect database type từ environment
    if db_type is None:
        if os.getenv("POSTGRES_HOST") or settings.postgres_host:
            db_type = "postgres"
        elif os.getenv("MYSQL_HOST") or settings.mysql_host:
            db_type = "mysql"
        else:
            logger.warning("Không tìm thấy cấu hình database trong environment variables")
            return None
    
    try:
        connector = SQLDatabaseConnector(db_type=db_type, **kwargs)
        return connector
    except Exception as e:
        logger.error(f"Không thể tạo database connector: {e}")
        return None


# Global instance (lazy initialization)
_sql_connector: Optional[SQLDatabaseConnector] = None


def get_sql_connector() -> Optional[SQLDatabaseConnector]:
    """
    Lấy global SQL database connector instance (singleton pattern)
    
    Returns
    -------
    Optional[SQLDatabaseConnector]
        SQLDatabaseConnector instance hoặc None
    """
    global _sql_connector
    if _sql_connector is None:
        _sql_connector = create_sql_connector()
    return _sql_connector


def reset_sql_connector():
    """Reset global SQL connector (dùng cho testing hoặc reconnect)"""
    global _sql_connector
    _sql_connector = None


def init_sql_connector(db_type: Optional[str] = None, **kwargs) -> Optional[SQLDatabaseConnector]:
    """
    Khởi tạo và lưu SQL connector vào global instance
    
    Parameters
    ----------
    db_type : Optional[str]
        Loại database: "postgres" hoặc "mysql" (mặc định: tự động detect)
    **kwargs
        Các tham số override cho connection
    
    Returns
    -------
    Optional[SQLDatabaseConnector]
        SQLDatabaseConnector instance hoặc None nếu không thể tạo
    """
    global _sql_connector
    if _sql_connector is None:
        _sql_connector = create_sql_connector(db_type=db_type, **kwargs)
    return _sql_connector

