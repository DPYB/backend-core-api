from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    DATABASE_URL: str = ""
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_HOST: str | None = None
    DB_PORT: int = 6543
    DB_NAME: str = "postgres"

    def model_post_init(self, __context: object) -> None:
        if not self.DATABASE_URL and self.DB_HOST and self.DB_USER and self.DB_PASSWORD:
            from urllib.parse import quote_plus

            encoded_user = quote_plus(self.DB_USER)
            encoded_password = quote_plus(self.DB_PASSWORD)
            self.DATABASE_URL = f"postgresql+asyncpg://{encoded_user}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        elif not self.DATABASE_URL:
            self.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres?options=-c%20search_path=core"

    # Authentication (Auth Server & OAuth JWT)
    AUTH_DISABLED: bool = False
    JWT_SECRET_KEY: str = "dont-paw-get-jwt-secret-change-in-prod-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    GUEST_TOKEN_EXPIRE_HOURS: int = 2
    DEMO_MEMBER_ID: str = "00000000-0000-0000-0000-000000000002"
    GOOGLE_CLIENT_ID: str | None = None
    KAKAO_CLIENT_ID: str | None = None

    # External APIs
    NL_API_CERT_KEY: str | None = None
    AI_AGENT_BASE_URL: str | None = None

    # App General
    ENV: str = "local"
    PORT: int = 8000
    PROJECT_NAME: str = "backend-core-api"
    CORS_ORIGINS: str = "*"


settings = Settings()
