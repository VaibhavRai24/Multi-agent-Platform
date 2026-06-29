from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise Multi-Agent RAG Platform"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENV: str = "dev"

    # Database setup defaults to SQLite if not provided
    DATABASE_URL: str = "sqlite:///./data/app.db"

    # JWT Config
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # OAuth2 Config
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Pinecone
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_HOST: Optional[str] = None
    PINECONE_INDEX_NAME: str = "rag-enterprise"

    # AWS
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: Optional[str] = None
    
    # OpenAI (legacy, kept for backward compat)
    OPENAI_API_KEY: Optional[str] = None

    # Google Gemini
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
