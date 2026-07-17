"""
Central application configuration.
All values are overridable via environment variables (.env file locally,
ECS task-definition environment / Secrets Manager in production).
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "AI Presales Assistant"
    ENV: str = "local"                      # local | staging | production
    DEBUG: bool = True

    # --- Database ---
    # In Docker Compose, DATABASE_URL is set directly.
    # In AWS, the CDK stack instead injects DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD
    # (DB_PASSWORD comes from Secrets Manager) and database_url below assembles the URL,
    # since ECS task secrets can't concatenate values from two different secrets at deploy time.
    DATABASE_URL: str = "postgresql://presales:presales@db:5432/presales"
    DB_HOST: str = ""
    DB_PORT: int = 5432
    DB_NAME: str = "presales"
    DB_USER: str = "presales_admin"
    DB_PASSWORD: str = ""

    @property
    def database_url(self) -> str:
        if self.DB_HOST and self.DB_PASSWORD:
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return self.DATABASE_URL

    # --- Redis (cache / job queue) ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Auth ---
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # --- AWS ---
    AWS_REGION: str = "me-central-1"        # UAE region; use me-south-1 for Bahrain/KSA proximity
    S3_BUCKET: str = "ai-presales-documents"
    USE_S3: bool = False                    # False = local disk storage for dev

    # --- LLM (extraction agent) ---
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-6"

    # --- Embeddings (policy RAG pipeline) ---
    # Anthropic doesn't serve embeddings directly; Voyage AI is Anthropic's
    # recommended embeddings partner for RAG use cases.
    VOYAGE_API_KEY: str = ""
    EMBEDDING_MODEL: str = "voyage-3.5"
    POLICY_CHUNK_SIZE: int = 1200          # characters per chunk
    POLICY_CHUNK_OVERLAP: int = 150
    POLICY_TOP_K: int = 5                   # chunks retrieved per query

    # --- CORS ---
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
