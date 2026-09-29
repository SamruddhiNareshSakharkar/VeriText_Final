import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    PROJECT_NAME: str = "VERITEXT"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment & Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "veritext-academic-secure-key-2026-prod-sample-change-in-env")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    
    # Database: Default to SQLite if PostgreSQL not active/reachable
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./veritext.db"
    )
    
    # Storage settings
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local")
    STORAGE_BASE_PATH: str = os.getenv("STORAGE_BASE_PATH", "./storage/uploads")
    REPORT_STORAGE_PATH: str = os.getenv("REPORT_STORAGE_PATH", "./storage/reports")
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "txt", "docx", "png", "jpg", "jpeg"]
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


settings = Settings()
