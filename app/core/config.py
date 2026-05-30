from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "NeoMarket B2B Service"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL_B2B: Optional[str] = None
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "db"
    DB_PORT: str = "5432"
    DB_NAME: str = "postgres"

    @field_validator("DATABASE_URL_B2B", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: any) -> any:
        if isinstance(v, str):
            return v
        
        return None

    def model_post_init(self, __context: any) -> None:
        if not self.DATABASE_URL_B2B:
            self.DATABASE_URL_B2B = f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_SECURE: bool = False
    B2B_SERVICE_KEY: str = "dev-service-key"

    MODERATION_SERVICE_URL: str

    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    ADMIN_FIRST_NAME: str
    ADMIN_LAST_NAME: str
    ADMIN_COMPANY_NAME: str
    ADMIN_INN: str

    B2B_PORT: int = 8080

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
