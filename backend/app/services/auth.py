"""注册事务和密码校验；CPU 密集的密码计算放在线程中。"""

import asyncio

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import hash_password, verify_password
from backend.app.models import User
from backend.app.repositories.users import UserRepository


class UsernameAlreadyExists(ValueError):
    """数据库唯一约束拒绝重复用户名，包括并发注册。"""


async def register_user(session: AsyncSession, username: str, password: str) -> User:
    password_hash = await asyncio.to_thread(hash_password, password)
    try:
        async with session.begin():
            user = await UserRepository(session).insert(username, password_hash)
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if (
            getattr(exc.orig, "sqlstate", None) == "23505"
            and constraint == "uq_users_username"
        ):
            raise UsernameAlreadyExists("用户名已存在。") from None
        raise
    return user


async def authenticate_user(
    session: AsyncSession, username: str, password: str
) -> User | None:
    user = await UserRepository(session).get_by_username(username)
    if user is None:
        return None
    matches = await asyncio.to_thread(verify_password, password, user.password_hash)
    return user if matches else None
