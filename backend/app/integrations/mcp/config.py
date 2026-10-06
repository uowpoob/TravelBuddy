"""高德 MCP 独立配置；本地调用不依赖数据库或模型配置。"""

from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr
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
