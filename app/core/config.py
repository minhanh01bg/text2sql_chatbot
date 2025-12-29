from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    
    # MongoDB
    mongodb_url: str
    mongodb_db_name: str
    
    # SQL Database (for text2sql)
    postgres_host: Optional[str] = None
    postgres_port: Optional[str] = "5432"
    postgres_db: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    
    mysql_host: Optional[str] = None
    mysql_port: Optional[str] = "3306"
    mysql_database: Optional[str] = None
    mysql_user: Optional[str] = None
    mysql_password: Optional[str] = None
    
    # Application
    app_name: str = "FastBase AI"
    app_version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

