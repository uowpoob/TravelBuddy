from pathlib import Path

from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env", override=False)


class AuthSettings(BaseSettings):
    """认证配置独立于模型和高德配置，密钥由部署环境提供。"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    AUTH_SECRET_KEY: SecretStr = SecretStr("")
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    database_dsn: SecretStr
    LANGGRAPH_PG_DSN: SecretStr = SecretStr("")

    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str
    DEEPSEEK_MODEL: str = "deepseek-flash"

    GD_API_KEY: SecretStr = SecretStr("")
    GD_JSAPI_KEY: str = ""
    GD_JSAPI_SECURITY_CODE: SecretStr = SecretStr("")

    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "TravelBuddy"

    @property
    def database_url(self) -> URL:
        params = conninfo_to_dict(self.database_dsn.get_secret_value())
        return URL.create(
            "postgresql+psycopg",
            username=params.pop("user", None),
            password=params.pop("password", None),
            host=params.pop("host", None),
            port=int(params.pop("port", "5432")),
            database=params.pop("dbname", None),
            query=params,
        )
