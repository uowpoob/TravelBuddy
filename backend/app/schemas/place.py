from pydantic import BaseModel, Field


class Place(BaseModel):
    """真实查询得到的地点；location 使用高德的经度,纬度格式。"""

    id: str
    name: str
    location: str
    category: str
    address: str = ""
    source: str = "amap"


class Candidates(BaseModel):
    """Researcher 的结构化输出，同时保存在 TripState.candidates。"""

    attractions: list[Place] = Field(default_factory=list)
    restaurants: list[Place] = Field(default_factory=list)
    hotels: list[Place] = Field(default_factory=list)
