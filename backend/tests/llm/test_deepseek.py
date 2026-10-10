"""检查真实 LangChain/OpenAI SDK 发送的请求，禁止外部网络调用。"""

import json
from contextlib import asynccontextmanager

import httpx
import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime
from openai import AsyncOpenAI

from backend.app.agents.context_analyst.agent import build_context_analyst_agent
from backend.app.agents.context_analyst.tools import CONTEXT_ANALYST_TOOL_NAMES
from backend.app.agents.planner.agent import build_planner_agent
from backend.app.agents.planner.tools import PLANNER_TOOL_NAMES
from backend.app.agents.researcher.agent import build_researcher_agent
from backend.app.agents.researcher.tools import RESEARCHER_TOOL_NAMES
from backend.app.agents.reviewer.agent import build_reviewer_agent
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.understand import UnderstandNode
from backend.app.integrations.llm import deepseek
from backend.app.schemas.structured_output import RequestUnderstanding
from backend.app.schemas.trip import TripRequest


@asynccontextmanager
async def model_transport(response, payloads, *, contents=None):
    def handle(request):
        payload = json.loads(request.content)
        payloads.append(payload)
        # 模拟 DeepSeek 的真实限制：思考模式拒绝强制工具调用。
        if payload.get("thinking", {}).get("type") != "disabled":
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Thinking mode does not support this tool_choice"
                    }
                },
            )
        message = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "mock-output",
                    "type": "function",
                    "function": {
                        "name": type(response).__name__,
                        "arguments": response.model_dump_json(),
                    },
                }
            ],
        }
        if payload.get("response_format") == {"type": "json_object"}:
            message = {
                "role": "assistant",
                "content": contents.pop(0) if contents else response.model_dump_json(),
            }
        return httpx.Response(
            200,
            json={
                "id": "mock-completion",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls"
                        if "tool_calls" in message
                        else "stop",
                        "message": message,
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
        client = AsyncOpenAI(
            api_key="unused",
            base_url="https://example.invalid",
            http_client=http_client,
        )
        yield deepseek.chat_model.model_copy(
            update={
                "root_async_client": client,
                "async_client": client.chat.completions,
                "disable_streaming": True,
                "max_retries": 0,
            }
        )


@pytest.mark.asyncio
async def test_understand_sends_json_mode_with_schema():
    response = RequestUnderstanding(
        new_trip=False,
        updated_fields=["destination_city"],
        trip_request=TripRequest(destination_city="杭州"),
    )
    payloads = []
    async with model_transport(response, payloads) as model:
        result = await UnderstandNode(model)(
            {"messages": [HumanMessage(content="我想去杭州玩")]},
            Runtime(context=TravelBuddyContext(user_id=1, conversation_id="test")),
            {"callbacks": []},
        )
    assert result["trip_request"].destination_city == "杭州"
    assert result["missing_fields"] == ["start_date", "days", "travelers", "transport"]
    assert len(payloads) == 1
    assert payloads[0]["thinking"] == {"type": "disabled"}
    assert payloads[0]["response_format"] == {"type": "json_object"}
    assert "tools" not in payloads[0]
    prompt = json.loads(payloads[0]["messages"][-1]["content"])
    assert "trip_request" in prompt["output_schema"]["properties"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_output", ["", '{"new_trip": true}'])
async def test_understand_retries_empty_or_invalid_json_once(bad_output):
    response = RequestUnderstanding(
        new_trip=False,
        updated_fields=["destination_city"],
        trip_request=TripRequest(destination_city="杭州"),
    )
    payloads = []
    async with model_transport(response, payloads, contents=[bad_output]) as model:
        result = await UnderstandNode(model)(
            {"messages": [HumanMessage(content="我想去杭州玩")]},
            Runtime(context=TravelBuddyContext(user_id=1, conversation_id="test")),
            {},
        )
    assert len(payloads) == 2
    assert result["trip_request"].destination_city == "杭州"


@pytest.mark.asyncio
async def test_invalid_model_output_stops_after_two_attempts_without_updating_state():
    response = RequestUnderstanding(
        new_trip=False,
        updated_fields=["destination_city"],
        trip_request=TripRequest(destination_city="杭州"),
    )
    payloads = []
    state = {"messages": [HumanMessage(content="我想去杭州玩")]}
    async with model_transport(response, payloads, contents=["", ""]) as model:
        with pytest.raises(OutputParserException):
            await UnderstandNode(model)(
                state,
                Runtime(context=TravelBuddyContext(user_id=1, conversation_id="test")),
                {},
            )
    assert len(payloads) == 2
    assert "trip_request" not in state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role", ["researcher", "context_analyst", "planner", "reviewer"]
)
async def test_all_agents_send_compatible_required_tool_request(
    role,
    confirmed_trip_state,
    monkeypatch,
):
    field = {
        "researcher": "candidates",
        "context_analyst": "travel_constraints",
        "planner": "itinerary",
        "reviewer": "review_result",
    }[role]
    response = confirmed_trip_state[field]
    payloads = []

    def unexpected_tool() -> str:
        raise AssertionError("本测试只检查模型请求，不执行业务工具")

    tools = [
        StructuredTool.from_function(
            unexpected_tool, name=name, description="测试占位工具"
        )
        for name in (
            *RESEARCHER_TOOL_NAMES,
            *CONTEXT_ANALYST_TOOL_NAMES,
            *PLANNER_TOOL_NAMES,
        )
    ]
    async with model_transport(response, payloads) as model:
        monkeypatch.setattr(deepseek, "chat_model", model)
        if role == "reviewer":
            agent = build_reviewer_agent()
        else:
            factory = {
                "researcher": build_researcher_agent,
                "context_analyst": build_context_analyst_agent,
                "planner": build_planner_agent,
            }[role]
            agent = factory(tools=tools)
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content="测试结构化输出")]}
        )
    assert result["structured_response"] == response
    assert len(payloads) == 1
    assert payloads[0]["thinking"] == {"type": "disabled"}
    assert payloads[0]["tool_choice"] == "required"
