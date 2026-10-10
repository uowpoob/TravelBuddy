"""高德 MCP 独立配置；本地调用不依赖数据库或模型配置。"""

from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AmapMCPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[4] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    api_key: SecretStr = Field(default=SecretStr(""), validation_alias="GD_API_KEY")
    server_url: AnyHttpUrl = Field(
        default="https://mcp.amap.com/mcp", validation_alias="GD_MCP_URL"
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        allow_inf_nan=False,
        validation_alias="GD_MCP_TIMEOUT_SECONDS",
    )
    redis_url: SecretStr = Field(
        default=SecretStr("redis://127.0.0.1:6379/0"), validation_alias="REDIS_URL"
    )
    cache_enabled: bool = Field(default=True, validation_alias="GD_MCP_CACHE_ENABLED")
    cache_namespace: str = Field(
        default="travelbuddy:dev:mcp:v1",
        min_length=1,
        validation_alias="GD_MCP_CACHE_NAMESPACE",
    )
    cache_ttl_seconds: int = Field(
        default=3600, ge=0, validation_alias="GD_MCP_CACHE_TTL_SECONDS"
    )
    cache_timeout_seconds: float = Field(
        default=0.5,
        gt=0,
        allow_inf_nan=False,
        validation_alias="GD_MCP_CACHE_TIMEOUT_SECONDS",
    )

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value().strip()
        if url and not url.startswith(("redis://", "rediss://", "unix://")):
            raise ValueError("REDIS_URL 必须使用 redis://、rediss:// 或 unix:// 协议。")
        return SecretStr(url)
