"""
登录会话相关路由。
"""

from functools import partial
import json
from typing import Optional, Union

from fastapi import APIRouter, Response
from fastapi.responses import RedirectResponse
from httpx import AsyncClient
from yarl import URL

from ....exceptions import AuthServerError
from ....utils.cookies import set_session_cookie
from ....config import CONFIRMATION_API_NAME, COOKIE_MAX_AGE



async def set_cookie(
    confirmation_url: Union[str, URL],
    state: str,
    redirect_uri: Union[str, URL, None] = None,
    *,
    http_clinet: Optional[AsyncClient] = None,
    **kwargs
) -> Response:
    """
    设置用户指定的 Cookie。

    Args:
        confirmation_url: 用于获取 Cookie 配置的 URL。
        state: 登录凭证。
        redirect_uri: 重定向目标。
        http_clinet: 用于发送请求的客户端，需要实现了与 AsyncClient 相同的 request 方法。
        kwargs: 其他传递给 http_clinet.request 的参数。
    """
    kwargs["method"] = "POST"
    kwargs["url"] = str(confirmation_url)
    kwargs.setdefault("params", {}).update({
        "state": state
    })

    if http_clinet:
        confirm_resp = await http_clinet.request(**kwargs)
    else:
        async with AsyncClient() as http_clinet:
            confirm_resp = await http_clinet.request(**kwargs)

    try:
        confirm_resp_json = confirm_resp.json()
        confirm_resp_data = confirm_resp_json.get("data")
    except (json.decoder.JSONDecodeError, AttributeError) as error:
        raise AuthServerError(f"Unexcepted json string: {confirm_resp.text}") from error

    if not (
        confirm_resp_data and
        isinstance(confirm_resp_data, dict) and
        isinstance(confirm_resp_data.get("cookies"), list)
    ):
        raise AuthServerError(f"Data not found: {confirm_resp_json}")

    if redirect_uri:
        response = RedirectResponse(url=str(redirect_uri))
    else:
        response = Response()
        response.status_code = 204

    for cookie in confirm_resp_data.get("cookies"):
        if not (
            (key := cookie.get("key")) and
            (value := cookie.get("value"))
        ):
            continue

        set_session_cookie(
            response,
            key=key,
            value=value,
            max_age=cookie.get("maxAge") or COOKIE_MAX_AGE,
        )

    print(response.headers)
    return response



def get_router(
    confirmation_url: str,
    *,
    http_clinet: Optional[AsyncClient] = None,
    **kwargs
) -> APIRouter:
    """
    获取 router。给路由器注册了用于 Set Cookie 的端口。

    Args:
        confirmation_url: 用于获取 Cookie 配置的 URL。
        http_clinet: 用于发送请求的客户端，需要实现了与 AsyncClient 相同的 request 方法。
        kwargs: 其他传递给 http_clinet.request 的参数。
    """
    router = APIRouter(prefix="/sessions", tags=["Sessions"])
    @router.get(f"/{CONFIRMATION_API_NAME}")
    async def set_cookie_endpoint(
        state: str,
        redirect_uri: Union[str, URL, None] = None,
    ) -> Response:
        """
        设置用户指定的 Cookie。

        Args:
            state: 登录凭证。
            redirect_uri: 重定向目标。
        """
        return await set_cookie(
            confirmation_url=confirmation_url,
            state=state,
            redirect_uri=redirect_uri,
            http_clinet=http_clinet,
            **kwargs
        )

    return router
