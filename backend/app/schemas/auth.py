from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class LoginRequest(BaseModel):
    username: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    password: str = Field(min_length=1, max_length=128, repr=False)


class RegisterRequest(LoginRequest):
    username: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)
    ]
    password: str = Field(min_length=8, max_length=128, repr=False)


class UserPublic(BaseModel):
    """允许返回给前端的用户字段；不包含密码或密码哈希。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


class InterestDescription(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    interest_description: str = Field(max_length=1000)


class TokenResponse(BaseModel):
    access_token: str = Field(repr=False)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserPublic
