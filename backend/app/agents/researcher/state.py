from langgraph.graph import MessagesState

from backend.app.schemas.place import Candidates
from backend.app.schemas.trip import TripRequest


class ResearcherState(MessagesState, total=False):
    """地点调研子图：内部消息记录模型与地点工具的交互。"""

    # 输入：用户的旅行需求。
    trip_request: TripRequest

    # 输出：筛选后的候选地点，交回主图。
    candidates: Candidates
