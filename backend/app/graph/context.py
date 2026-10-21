from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class TravelBuddyContext:
    """主图和 Agent 子图共用的运行上下文，通过 runtime.context 读取。

    保存运行资源，不放进 State 或 checkpoint。恢复时由入口重新传入。
    模型和工具在创建各个 Agent 时绑定。
    db 仅由主图的 save 节点使用，预览阶段可以不传；实际保存必须传入。
    传入 Save 专用且未开启事务的 session，由保存服务负责提交或回滚。
    """

    user_id: int
    conversation_id: str
    db: AsyncSession | None = field(default=None, repr=False, compare=False)
    interest_description: str = ""
