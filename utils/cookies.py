"""
Cookie 操作辅助函数。
"""

from numbers import Real
from typing import Optional

from starlette.responses import Response

from ..config import COOKIE_MAX_AGE


def set_session_cookie(
    response: Response,
    key: str,
    value: str,
    max_age: Real = COOKIE_MAX_AGE,
    domain: Optional[str] = None,
) -> None:
    """
    设置登录会话 Cookie。

    Args:
        response: Starlette Response 对象
        sid: 会话标识符
        max_age: 有效期秒数，默认使用配置的 COOKIE_MAX_AGE
    """
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        domain=domain,
        httponly=True,
        secure=True,
        samesite="Lax",
    )
