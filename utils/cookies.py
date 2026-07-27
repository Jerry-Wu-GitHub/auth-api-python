"""
Cookie 操作辅助函数。
"""

from numbers import Real
from typing import Optional

from starlette.responses import Response

from ..config import COOKIE_MAX_AGE, SESSION_COOKIE_NAME, DEFAULT_COOKIE_DOMAIN


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
        key=SESSION_COOKIE_NAME,
        value=value,
        max_age=max_age,
        domain=domain,
        httponly=True,
        secure=True,
        samesite="Lax",
    )


def delete_session_cookie(response: Response) -> None:
    """
    删除客户端登录会话 Cookie（设置过期时间为过去）。
    """
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        domain=DEFAULT_COOKIE_DOMAIN,
        httponly=True,
        secure=True,
        samesite="Lax",
    )
