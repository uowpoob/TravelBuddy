"""密码哈希和固定 HS256 算法的 JWT 签发/校验。"""

import base64
import binascii
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from backend.app.core.config import AuthSettings

PASSWORD_ITERATIONS = 600000
TOKEN_ALGORITHM = "HS256"
TOKEN_ISSUER = "travelbuddy"
TOKEN_AUDIENCE = "travelbuddy-api"
MAX_USER_ID = 2**63 - 1


class AuthConfigurationError(ValueError):
    """认证配置尚未准备好；不包含密钥值。"""


class InvalidAccessToken(ValueError):
    """令牌缺失、无效或过期。"""


def hash_password(password: str) -> str:
    """随机盐 + PBKDF2-SHA256，与现有 CLI 调试账号哈希格式兼容。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_text = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"$pbkdf2-sha256${PASSWORD_ITERATIONS}${salt_text}${digest_text}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        prefix, scheme, rounds, salt_text, digest_text = password_hash.split("$")
        iterations = int(rounds)
        if prefix or scheme != "pbkdf2-sha256" or iterations != PASSWORD_ITERATIONS:
            return False
        salt = base64.b64decode(salt_text, altchars=b"-_", validate=True)
        expected = base64.b64decode(digest_text, altchars=b"-_", validate=True)
        if len(salt) != 16 or len(expected) != 32:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, binascii.Error):
        return False


def require_auth_configuration(settings: AuthSettings) -> None:
    secret = settings.AUTH_SECRET_KEY.get_secret_value()
    if secret.isspace() or len(secret.encode("utf-8")) < 32:
        raise AuthConfigurationError("请配置至少 32 字节的 AUTH_SECRET_KEY。")


def create_access_token(user_id: int, settings: AuthSettings) -> str:
    require_auth_configuration(settings)
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": now + timedelta(minutes=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES),
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
        },
        settings.AUTH_SECRET_KEY.get_secret_value(),
        algorithm=TOKEN_ALGORITHM,
    )


def access_token_user_id(token: str, settings: AuthSettings) -> int:
    require_auth_configuration(settings)
    try:
        payload = jwt.decode(
            token,
            settings.AUTH_SECRET_KEY.get_secret_value(),
            algorithms=[TOKEN_ALGORITHM],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={"require": ["sub", "exp", "iss", "aud"]},
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise InvalidAccessToken("登录凭证无效或已过期。") from None
    if not 1 <= user_id <= MAX_USER_ID:
        raise InvalidAccessToken("登录凭证无效或已过期。")
    return user_id
