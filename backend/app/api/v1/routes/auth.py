from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import (
    authentication_error,
    get_auth_settings,
    get_current_user,
    get_session,
)
from backend.app.core.config import AuthSettings
from backend.app.core.security import create_access_token
from backend.app.models import User
from backend.app.schemas.auth import (
    InterestDescription,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from backend.app.services.auth import (
    UsernameAlreadyExists,
    authenticate_user,
    register_user,
    update_interest_description,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=201)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserPublic:
    try:
        user = await register_user(session, payload.username, payload.password)
    except UsernameAlreadyExists:
        raise HTTPException(status_code=409, detail="用户名已存在。") from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    return UserPublic.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> TokenResponse:
    try:
        user = await authenticate_user(session, payload.username, payload.password)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="数据库暂时不可用，请稍后重试。"
        ) from None
    if user is None:
        raise authentication_error("账号或密码错误。")
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        access_token=create_access_token(user.id, settings),
        expires_in=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic)
async def me(
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
) -> UserPublic:
    response.headers["Cache-Control"] = "no-store"
    return UserPublic.model_validate(user)


@router.get("/me/interests", response_model=InterestDescription)
async def get_interests(
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
) -> InterestDescription:
    response.headers["Cache-Control"] = "no-store"
    return InterestDescription(interest_description=user.interest_description or "")


@router.put("/me/interests", response_model=InterestDescription)
async def put_interests(
    payload: InterestDescription,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InterestDescription:
    response.headers["Cache-Control"] = "no-store"
    try:
        await update_interest_description(session, user, payload.interest_description)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="兴趣描述保存失败，请稍后重试。"
        ) from None
    return payload
