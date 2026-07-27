"""
AuthClient 实现，提供 FastAPI 依赖注入，用于在业务微服务中验证登录态。
"""

from __future__ import annotations

from functools import partial
from typing import Callable, Optional, Self, Union

import httpx
from fastapi import HTTPException, Request, APIRouter
from starlette import status
from yarl import URL

from ..config import SESSION_COOKIE_NAME, CONFIRMATION_API_NAME
from ..exceptions import AuthServerUnavailable, NotLoggedError
from .account import Account
from ..routes.api import router_getters


class AuthClient:
    """
    认证客户端，用于在其他 FastAPI 微服务中集成身份验证。

    使用方法:
        auth_client = AuthClient(
            base_url="https://myapp.ms.show",
            auth_homepage="https://auth.ms.show"
        )
        router = APIRouter(dependencies=[Depends(auth_client.get_auth_dependency("/some-path"))])
    """

    def __init__(
        self,
        base_url: Union[str, URL],
        auth_homepage: Union[str, URL],
        *,
        auth_api_version: str = "v1",
        http_client: Optional[httpx.AsyncClient] = None,
        **kwargs
    ):
        """
        初始化认证客户端。

        Args:
            base_url: 当前微服务的 Base URL
            auth_homepage: 认证微服务主页 URL
            auth_api_version: 认证微服务的版本
            http_client (httpx.AsyncClient): An HTTP client similar to `httpx.AsyncClient`, used for sending requests.
            kwargs: The initialization parameters passed to `http_client`.
        """
        self.base_url: URL = URL(base_url)

        # 认证微服务
        self.auth_homepage: URL = URL(auth_homepage)
        self.auth_api_base_url = self.auth_homepage / f"api/{auth_api_version}"

        # HTTP Client
        self._http_client_is_local = http_client is None
        if self._http_client_is_local:
            http_client = httpx.AsyncClient(**kwargs)
        self._http_client = http_client
        self._kwargs = kwargs


    async def __aenter__(self) -> Self:
        if self._http_client_is_local:
            await self._http_client.__aenter__()
        return self


    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._http_client_is_local:
            await self._http_client.__aexit__(exc_type, exc_val, exc_tb)


    async def aclose(self) -> None:
        """Close the client within the instance."""
        if self._http_client_is_local:
            await self._http_client.aclose()


    def get_router(self, api_version: str) -> APIRouter:
        """
        返回需要注册到根路由的 API URL。
        """
        if api_version not in router_getters:
            raise KeyError(
                f"Version not found: {api_version}. "
                f"Available versions: {list(router_getters.keys())}"
            )
        get_router = router_getters[api_version]
        return get_router(
            confirmation_url=self.auth_api_base_url / "sessions" / CONFIRMATION_API_NAME,
            http_clinet=self._http_client
        )


    def _get_auth_api_url(self, subpath: str) -> URL:
        """
        拼接认证微服务的 API URL。
        """
        return self.auth_api_base_url / subpath


    async def request(self, subpath: str, **kwargs) -> httpx.Response:
        """
        使用 self._http_client，向 API 端点发送请求。

        Args:
            subpath: 认证服务的 API 端点。
            kwargs: 传递给 `http_client.request` 的其他参数。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
        """
        kwargs["url"] = str(self._get_auth_api_url(subpath))
        try:
            return await self._http_client.request(**kwargs)
        except Exception as error:
            raise AuthServerUnavailable("认证服务不可用") from error


    async def _verify_auth(self, current_path: str, request: Request) -> None:
        """
        验证登录态依赖：
        - 从请求中提取 jerry_sid Cookie
        - 向认证服务请求用户信息
        - 若未登录，重定向到认证主页并附带 redirect 参数
        """
        # 提取 Cookie
        cookies = {}
        if "jerry_sid" in request.cookies:
            cookies["jerry_sid"] = request.cookies["jerry_sid"]

        # 调用认证服务
        try:
            resp = await self.request(
                "users/me",
                method="GET",
                cookies=cookies,
                follow_redirects=False
            )
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="认证服务不可用"
            ) from error

        if resp.status_code == status.HTTP_200_OK:
            # 登录有效，可将用户信息注入 request.state（可选）
            user_data = resp.json().get("data")
            request.state.user = user_data
            return

        # 未登录或其他错误，重定向到认证主页
        full_redirect_url = self.base_url / current_path
        login_url = self.auth_homepage.with_query({"redirect": str(full_redirect_url)})
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": login_url},
        )


    def redirect_to_auth(
        self,
        current_path: str,
    ) -> None:
        """
        引发一个重定向到登录页面的 HTTPException。
        """
        full_redirect_url = self.base_url / current_path
        login_url = self.auth_homepage.with_query({"redirect": str(full_redirect_url)})
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": login_url},
        )


    async def _get_current_account(
        self,
        current_path: str,
        request: Request,
    ) -> Account:
        """
        验证登录态依赖：根据请求中的 sid，获得账号对象。
        1. 从请求中提取 jerry_sid Cookie
        2. 向认证服务发送需要权限的请求
        3. 若未登录，重定向到认证主页并附带 redirect 参数
        """
        sid=request.cookies.get(SESSION_COOKIE_NAME)
        if not sid:
            self.redirect_to_auth(current_path)

        account = Account(
            auth_client=self,
            sid=sid
        )

        try:
            await account.keep_alive()

        except AuthServerUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="认证服务不可用"
            ) from error

        except NotLoggedError:
            # 未登录，重定向到认证主页
            self.redirect_to_auth(current_path)

        return account


    def get_auth_dependency(self, current_path: str) -> Callable[[Request], Account]:
        """
        工厂方法，返回一个 FastAPI 依赖函数，用于验证请求的登录态。

        Args:
            current_path: 当前路径（如 "/users/me"），用于拼接完整 redirect URL

        Returns:
            FastAPI 依赖函数。该函数接受 Request 作为输入，Account 作为输出。
        """
        return partial(self._get_current_account, current_path)
