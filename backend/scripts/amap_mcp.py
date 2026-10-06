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
    listing = commands.add_parser("list", help="列出工具名称、描述和参数 schema")
    listing.add_argument(
        "--output", type=Path, help="将完整工具列表保存为 UTF-8 JSON 文件"
    )
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
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"已获取 {len(tools)} 个高德 MCP 工具，保存到：{args.output}")
            for tool in tools:
                print(f"- {tool.name}")
            return 0
        exit_code = 0
    else:
        result = await client.call_tool(args.name, args.tool_arguments)
        output = result.model_dump(mode="json", by_alias=True)
        exit_code = 1 if result.is_error else 0
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    # Windows 重定向输出时也使用 UTF-8，避免中文工具说明出现乱码。
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
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
    except OSError:
        print("无法保存工具列表，请检查输出路径和写入权限。", file=sys.stderr)
        code = 1
    sys.exit(code)
