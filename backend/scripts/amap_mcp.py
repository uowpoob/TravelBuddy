"""本地列出或调用高德 MCP 工具，不启动 HTTP 服务或 Agent。"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.app.core.runtime import loop_factory
from backend.app.integrations.mcp import AmapMCPClient, AmapMCPError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地调用高德 MCP 服务")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="列出工具名称、描述和参数 schema")
    call = commands.add_parser("call", help="调用指定工具")
    call.add_argument("name", help="list 命令返回的工具名称")
    arguments = call.add_mutually_exclusive_group()
    arguments.add_argument("--arguments", help="JSON 对象形式的工具参数")
    arguments.add_argument("--arguments-file", type=Path, help="UTF-8 JSON 参数文件")
    args = parser.parse_args()

    args.tool_arguments = {}
    if args.command == "call":
        try:
            raw = (
                args.arguments_file.read_text(encoding="utf-8-sig")
                if args.arguments_file is not None
                else args.arguments or "{}"
            )
        except (OSError, UnicodeError):
            parser.error("无法读取参数文件，请使用 UTF-8 JSON 文件。")
        try:
            args.tool_arguments = json.loads(raw)
        except json.JSONDecodeError:
            parser.error("工具参数必须是有效的 JSON。")
        if not isinstance(args.tool_arguments, dict):
            parser.error("工具参数必须是 JSON 对象。")
    return args


async def main(args: argparse.Namespace) -> int:
    client = AmapMCPClient()
    output: Any
    if args.command == "list":
        tools = await client.list_tools()
        output = [tool.model_dump(mode="json", by_alias=True) for tool in tools]
        exit_code = 0
    else:
        result = await client.call_tool(args.name, args.tool_arguments)
        output = result.model_dump(mode="json", by_alias=True)
        exit_code = 1 if result.is_error else 0
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    parsed_args = parse_args()
    try:
        code = asyncio.run(main(parsed_args), loop_factory=loop_factory)
    except ValidationError:
        print(
            "高德 MCP 配置无效，请检查 GD_MCP_URL 和 GD_MCP_TIMEOUT_SECONDS。",
            file=sys.stderr,
        )
        code = 1
    except AmapMCPError as exc:
        print(str(exc), file=sys.stderr)
        code = 1
    sys.exit(code)
