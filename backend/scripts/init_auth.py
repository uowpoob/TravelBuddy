"""生成本地 JWT 签名密钥；保留现有配置，不输出任何密钥。"""

import io
import os
import re
import secrets
import sys
from pathlib import Path

from dotenv import dotenv_values


def valid_secret(value: str | None) -> bool:
    return bool(value and not value.isspace() and len(value.encode("utf-8")) >= 32)


def main() -> int:
    external_key = next(
        (
            value
            for name, value in os.environ.items()
            if name.upper() == "AUTH_SECRET_KEY"
        ),
        None,
    )
    if external_key is not None:
        if not valid_secret(external_key):
            print("环境变量 AUTH_SECRET_KEY 无效，请使用至少 32 字节的随机密钥。")
            return 1
        print("AUTH_SECRET_KEY 已由环境变量配置，保留现有密钥。")
        return 0

    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        print("请先从 .env.example 创建本地 .env 并填写数据库配置。")
        return 1
    original = path.read_bytes()
    contents = original.decode("utf-8-sig")
    values = dotenv_values(stream=io.StringIO(contents))
    existing_name = next(
        (name for name in values if name.upper() == "AUTH_SECRET_KEY"), None
    )
    existing = values.get(existing_name) if existing_name is not None else None
    if valid_secret(existing):
        print("本地 AUTH_SECRET_KEY 已配置，保留现有密钥。")
        return 0
    if existing:
        print("本地 AUTH_SECRET_KEY 长度不足，请手动更换至少 32 字节的随机密钥。")
        return 1

    newline = "\r\n" if b"\r\n" in original else "\n"
    key = secrets.token_urlsafe(48)
    entry = f"AUTH_SECRET_KEY={key}"
    if existing_name is not None:
        updated = re.sub(
            r"(?im)^[ \t]*(?:export[ \t]+)?AUTH_SECRET_KEY[ \t]*=[^\r\n]*",
            entry,
            contents,
        )
    else:
        updated = (
            contents + ("" if contents.endswith("\n") else newline) + entry + newline
        )
    bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    path.write_bytes(bom + updated.encode("utf-8"))
    print("已在本地 .env 配置随机 AUTH_SECRET_KEY。请重启后端加载配置。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
