"""将高德 MCP 工具描述与客户端调用适配为 LangChain 异步工具。"""

import json
from collections.abc import Sequence
from copy import deepcopy
from typing import Any

from langchain_core.tools import StructuredTool, ToolException
from mcp.types import CallToolResult, Tool

from backend.app.integrations.mcp.client import AmapMCPClient, AmapMCPError


def _result_content(result: CallToolResult) -> str:
    """向模型提供文本及结构化数据；没有文本时保留完整 JSON 表示。"""
    parts = [block.text for block in result.content if block.type == "text"]
    if result.structured_content is not None:
        parts.append(json.dumps(result.structured_content, ensure_ascii=False))
    return "\n".join(parts) or result.model_dump_json(by_alias=True)


def _adapt_tool(tool: Tool, client: AmapMCPClient) -> StructuredTool:
    # 每个工具单独创建闭包，避免循环中所有调用都绑定到最后一个工具。
    async def invoke_tool(**arguments: Any) -> tuple[str, dict[str, Any]]:
        try:
            result = await client.call_tool(tool.name, arguments)
        except AmapMCPError as exc:
            raise ToolException(str(exc)) from None

        content = _result_content(result)
        if result.is_error:
            raise ToolException(f"高德工具 {tool.name} 执行失败：{content}")

        # content 交给模型；artifact 保存成功调用的完整 MCP 响应。
        artifact = result.model_dump(mode="json", by_alias=True)
        return content, artifact

    return StructuredTool.from_function(
        name=tool.name,
        description=tool.description or f"调用高德 MCP 工具 {tool.name}",
        args_schema=deepcopy(tool.input_schema),
        coroutine=invoke_tool,
        infer_schema=False,
        response_format="content_and_artifact",
        handle_tool_error=True,
        metadata={"mcp_server": "amap", "mcp_tool": tool.name},
    )


def adapt_amap_tools(
    tools: Sequence[Tool], client: AmapMCPClient
) -> list[StructuredTool]:
    """适配已经发现的工具；仅创建工具对象，不访问网络或调用模型。

    保留服务端 JSON Schema，不根据 **arguments 重新推断参数。
    工具通过 ainvoke 执行，成功响应的原始数据保存在 ToolMessage.artifact。
    """
    return [_adapt_tool(tool, client) for tool in tools]


async def load_amap_tools(client: AmapMCPClient) -> list[StructuredTool]:
    """先通过 MCP 发现工具，再创建可供 Agent 绑定的 LangChain 工具。

    这里只执行工具发现，业务工具将在 Agent 或调用方实际调用时执行。
    """
    tools = await client.list_tools()
    return adapt_amap_tools(tools, client)
