"""在终端运行真实旅行图，支持澄清、确认、保存和持久化恢复。"""

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import math
import os
import re
import secrets
import sys
import traceback
from dataclasses import dataclass
from urllib.parse import quote, quote_plus
from uuid import UUID, uuid4

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command
from psycopg import Error as PsycopgError
from psycopg.conninfo import conninfo_to_dict
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.agents.builder import build_agents
from backend.app.core.config import Settings
from backend.app.core.runtime import loop_factory
from backend.app.db.session import create_engine
from backend.app.graph.builder import build_trip_graph
from backend.app.graph.checkpoints import open_checkpointer
from backend.app.graph.context import TravelBuddyContext
from backend.app.graph.nodes.confirm import format_itinerary
from backend.app.integrations.mcp import AmapMCPClient, AmapMCPSettings
from backend.app.models import Conversation, User
from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.trip import TripRequest

NODE_LABELS = {
    "understand": "理解需求",
    "clarify": "补充需求",
    "researcher": "地点调研",
    "context_analyst": "天气与出行约束",
    "planner": "规划行程",
    "reviewer": "审核行程",
    "confirm": "用户确认",
    "save": "保存行程",
}


class ChatSetupError(ValueError):
    """可直接展示的本地调试入口配置错误。"""


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("必须是正整数")
    return number


def positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("必须是有限的正数")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="在终端交互测试 TravelBuddy 旅行图")
    parser.add_argument("--message", help="第一条需求，或已有会话当前暂停处的回答")
    parser.add_argument(
        "--user-id", type=positive_int, help="使用已有用户；省略时创建本地调试用户"
    )
    parser.add_argument(
        "--conversation-id", type=UUID, help="重新打开已有会话，必须同时提供 --user-id"
    )
    parser.add_argument(
        "--once", action="store_true", help="只执行 --message 这一轮，暂停或完成后退出"
    )
    parser.add_argument(
        "--timeout",
        type=positive_seconds,
        default=300.0,
        help="每轮执行超时秒数，默认 300",
    )
    parser.add_argument(
        "--recursion-limit",
        type=positive_int,
        default=50,
        help="每轮图执行步数上限，默认 50",
    )
    parser.add_argument(
        "--debug", action="store_true", help="报错时显示调用栈位置，隐藏密钥和连接串"
    )
    args = parser.parse_args(argv)
    if args.conversation_id is not None and args.user_id is None:
        parser.error("--conversation-id 必须同时提供 --user-id")
    if args.message is not None:
        args.message = args.message.strip()
        if not args.message:
            parser.error("--message 不能为空")
    if args.once and args.message is None:
        parser.error("--once 必须同时提供 --message")
    return args


def safe_diagnostic(error: object) -> str:
    """保留错误原因；隐藏配置秘密、鉴权 URL 和校验失败的原始输入。"""
    if isinstance(error, ValidationError):
        details = error.errors(
            include_input=False, include_context=False, include_url=False
        )
        text = json.dumps(details, ensure_ascii=False)
    else:
        text = str(error)
    secret_values = set()
    for name, value in os.environ.items():
        if not value or not any(
            part in name.lower()
            for part in ("key", "dsn", "password", "token", "secret")
        ):
            continue
        secret_values.add(value)
        if "dsn" in name.lower():
            try:
                password = conninfo_to_dict(value).get("password")
                if password:
                    secret_values.add(password)
            except (ValueError, PsycopgError):
                pass
    for value in sorted(secret_values, key=len, reverse=True):
        for variant in (value, quote(value, safe=""), quote_plus(value)):
            text = text.replace(variant, "[REDACTED]")
    text = re.sub(r"\b(?:https?|postgres(?:ql)?)://[^\s'\"<>]+", "[URL REDACTED]", text)
    text = re.sub(r"(?i)\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(
        r"(?i)\b(password|passwd|api[_-]?key|key|token|secret|authorization)\b"
        r"(\s*['\"]?\s*[:=]\s*)(?:'[^']*'|\"[^\"]*\"|[^\s,;}\]]+)",
        r"\1\2[REDACTED]",
        text,
    )
    return text[:2000]


def show_error(error: Exception, *, prefix: str, debug: bool, file=None):
    print(f"{prefix}（{type(error).__name__}）：{safe_diagnostic(error)}", file=file)
    if debug:
        # 只输出文件、行号和函数名，不输出栈帧变量、源码或原始异常链。
        for frame in traceback.extract_tb(error.__traceback__)[-12:]:
            print(f"  {frame.filename}:{frame.lineno} in {frame.name}", file=file)


class ToolProgress(AsyncCallbackHandler):
    """只显示真实 MCP 工具的名称，不打印参数、原始响应或凭据。"""

    def __init__(self):
        self.names: dict[UUID, str] = {}

    async def on_tool_start(self, serialized, input_str, *, run_id, **kwargs):
        name = (serialized or {}).get("name", kwargs.get("name", ""))
        if isinstance(name, str) and name.startswith("maps_"):
            self.names[run_id] = name
            print(f"[工具开始] {name}", flush=True)

    async def on_tool_end(self, output, *, run_id, **kwargs):
        name = self.names.pop(run_id, None)
        if name:
            print(f"[工具完成] {name}", flush=True)

    async def on_tool_error(self, error, *, run_id, **kwargs):
        name = self.names.pop(run_id, None)
        if name:
            print(f"[工具失败] {name}（{type(error).__name__}）", flush=True)


@dataclass(frozen=True)
class ChatIdentity:
    user_id: int
    conversation_id: str


def debug_password_hash() -> str:
    # 随机秘密不保存或展示；此用户只供本地 CLI 调试，不提供登录密码。
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", secrets.token_bytes(32), salt, 600_000)
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_text = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"$pbkdf2-sha256$600000${salt_text}${digest_text}"


async def prepare_conversation(factory, args) -> ChatIdentity:
    async with factory() as session, session.begin():
        if args.user_id is None:
            user = User(
                username=f"graph-debug-{uuid4().hex}",
                password_hash=await asyncio.to_thread(debug_password_hash),
            )
            session.add(user)
            await session.flush()
        else:
            user = await session.get(User, args.user_id)
            if user is None:
                raise ChatSetupError(
                    "指定用户不存在；可省略 --user-id 创建本地调试用户。"
                )
        if args.conversation_id is None:
            conversation = Conversation(
                user_id=user.id,
                title=(args.message or "后端图调试")[:100],
            )
            session.add(conversation)
            await session.flush()
        else:
            conversation = await session.get(Conversation, str(args.conversation_id))
            if conversation is None or conversation.user_id != user.id:
                raise ChatSetupError("会话不存在或不属于指定用户。")
        identity = ChatIdentity(user.id, conversation.id)
    return identity


def show_interrupt(snapshot):
    if not snapshot.interrupts:
        return
    payload = snapshot.interrupts[0].value
    if isinstance(payload, dict):
        print()
        if payload.get("summary"):
            print(payload["summary"])
        print(f"助手：{payload.get('question', '请继续回答。')}")
    else:
        print(f"助手：{payload}")


def show_state(snapshot):
    values = snapshot.values
    request = TripRequest.model_validate(values.get("trip_request") or {})
    if values.get("trip_request") is None:
        print("[当前需求] 尚未完成需求提取；understand 成功后才会填充。")
    else:
        print(
            "[当前需求] "
            + json.dumps(request.model_dump(mode="json"), ensure_ascii=False)
        )
    print(f"[已记录消息] {len(values.get('messages', []))} 条")
    if values.get("itinerary") is not None:
        print(
            format_itinerary(
                Itinerary.model_validate(values["itinerary"]),
                Candidates.model_validate(values.get("candidates") or {}),
                request,
            )
        )
    print(f"[待执行节点] {', '.join(snapshot.next) or '无'}")
    for task in snapshot.tasks:
        if task.error:
            print(f"[失败节点] {task.name}：{safe_diagnostic(task.error)}")
    if values.get("saved_itinerary_id") is not None:
        print(
            f"[已保存] 行程 ID={values['saved_itinerary_id']}，版本={values.get('saved_itinerary_version')}"
        )


async def stream_turn(graph, factory, identity, config, graph_input, timeout):
    # 每轮新建专用 session，不复用准备用户/会话时的事务。
    async with factory() as session:
        context = TravelBuddyContext(
            user_id=identity.user_id,
            conversation_id=identity.conversation_id,
            db=session,
        )
        async with asyncio.timeout(timeout):
            async for updates in graph.astream(
                graph_input,
                config=config,
                context=context,
                stream_mode="updates",
                durability="sync",
            ):
                for node, fields in updates.items():
                    if node in NODE_LABELS:
                        print(f"[节点完成] {NODE_LABELS[node]}", flush=True)
                        if node == "save":
                            print(
                                f"[已保存] 行程 ID={fields['saved_itinerary_id']}，版本={fields['saved_itinerary_version']}"
                            )
    return await graph.aget_state(config)


async def chat_loop(graph, factory, identity, args, *, read_input=None) -> int:
    read_input = read_input or input
    config = {
        "configurable": {"thread_id": identity.conversation_id},
        "recursion_limit": args.recursion_limit,
        "callbacks": [ToolProgress()],
    }
    snapshot = await graph.aget_state(config)
    if args.conversation_id is not None and not snapshot.values:
        raise ChatSetupError("找不到该会话的 checkpoint；请确认 PG 配置或新建会话。")
    print(f"用户 ID：{identity.user_id}")
    print(f"会话 ID：{identity.conversation_id}")
    print("输入需求或回答；/state 查看状态，/retry 重试失败步骤，/quit 退出。")
    pending_message = args.message
    while True:
        show_interrupt(snapshot)
        if snapshot.next and not snapshot.interrupts:
            print("当前流程有待完成步骤，请输入 /retry 继续，或 /quit 退出。")
        if pending_message is not None:
            answer, pending_message = pending_message, None
            print(f"你：{answer}")
        else:
            try:
                answer = read_input("你> ").strip()
            except EOFError:
                return 0
        if not answer:
            continue
        if answer == "/quit":
            return 0
        if answer == "/state":
            show_state(snapshot)
            if args.once:
                return 0
            continue
        if snapshot.interrupts:
            if answer == "/retry":
                print("当前正在等待回答，请回答助手的问题。")
                if args.once:
                    return 1
                continue
            graph_input = Command(resume=answer)
        elif snapshot.next:
            if answer != "/retry":
                print("请先用 /retry 完成当前步骤。")
                if args.once:
                    return 1
                continue
            graph_input = None
        else:
            if answer == "/retry":
                print("当前没有失败步骤，请输入新的旅行需求。")
                if args.once:
                    return 1
                continue
            graph_input = {"messages": [HumanMessage(content=answer)]}
        try:
            snapshot = await stream_turn(
                graph, factory, identity, config, graph_input, args.timeout
            )
        except GraphRecursionError:
            print("执行达到步数上限，请用 /state 检查当前状态。")
            if args.once:
                return 1
            snapshot = await graph.aget_state(config)
        except TimeoutError:
            print("本轮执行超时，可用 /retry 从 checkpoint 重试。")
            if args.once:
                return 1
            snapshot = await graph.aget_state(config)
        except Exception as exc:  # noqa: BLE001 -- sanitized CLI error boundary
            show_error(exc, prefix="本轮执行失败", debug=args.debug)
            if args.once:
                return 1
            snapshot = await graph.aget_state(config)
        if args.once:
            show_interrupt(snapshot)
            return 0


async def main(args) -> int:
    settings = Settings()
    amap_settings = AmapMCPSettings()
    if not all(
        value.strip()
        for value in (
            settings.DEEPSEEK_API_KEY,
            settings.DEEPSEEK_BASE_URL,
            settings.DEEPSEEK_MODEL,
            amap_settings.api_key.get_secret_value(),
        )
    ):
        raise ChatSetupError("请在 .env 中填写 DeepSeek 配置和 GD_API_KEY。")
    if (
        args.conversation_id is not None
        and not settings.LANGGRAPH_PG_DSN.get_secret_value().strip()
    ):
        raise ChatSetupError("跨进程恢复已有会话需要配置 LANGGRAPH_PG_DSN。")
    engine = create_engine(settings)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with open_checkpointer(settings) as saver:
            print(f"Checkpoint：{type(saver).__name__}", flush=True)
            print("正在发现高德工具并初始化 Agent…", flush=True)
            agents = await build_agents(AmapMCPClient(amap_settings))
            graph = build_trip_graph(agents, checkpointer=saver)
            identity = await prepare_conversation(factory, args)
            return await chat_loop(graph, factory, identity, args)
    finally:
        await engine.dispose()


def cli(argv=None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(main(args), loop_factory=loop_factory)
    except KeyboardInterrupt:
        print("\n已退出；配置 PG checkpoint 后可使用会话 ID 恢复。")
        return 130
    except ChatSetupError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 -- sanitized CLI error boundary
        show_error(exc, prefix="启动失败", debug=args.debug, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING)
    sys.exit(cli())
