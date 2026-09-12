from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres?options=-c%20search_path=core"

    # Authentication
    AUTH_APP_CLIENT_ID: str | None = None
    COGNITO_USER_POOL_ID: str | None = None
    COGNITO_REGION: str = "ap-northeast-2"
    AUTH_DISABLED: bool = False

    # External APIs
    NL_API_CERT_KEY: str | None = None
    AI_AGENT_BASE_URL: str | None = None

    # App General
    ENV: str = "local"
    PORT: int = 8000
    PROJECT_NAME: str = "backend-core-api"
    CORS_ORIGINS: str = "*"


settings = Settings()
