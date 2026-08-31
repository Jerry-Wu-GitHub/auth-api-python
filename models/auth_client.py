"""
AuthClient 实现，提供 FastAPI 依赖注入，用于在业务微服务中验证登录态。
"""

from __future__ import annotations

from functools import partial
from typing import Callable, Optional, Self, Union

from fake_useragent import UserAgent
from fastapi import HTTPException, Request, APIRouter
import httpx
from starlette import status
from yarl import URL

from ..config import CONFIRMATION_API_NAME
from ..exceptions import (
    PermissionDeniedException,
    UpstreamUnavailableException,
    UnauthorizedException,
)
from .account import Account
from ..routes.api import router_getters
from .user import UserInfo


class AuthClient:
    """
    认证客户端，用于在其他 FastAPI 微服务中集成身份验证。

    使用方法:
        auth_client = AuthClient(
            homepage="https://myapp.com",
            auth_homepage="https://auth.com"
        )
        router = APIRouter(dependencies=[Depends(auth_client.get_auth_dependency("/some-path"))])
    """

    def __init__(
        self,
        homepage: Union[str, URL],
        *,
        auth_homepage: Optional[Union[str, URL]] = None,
        auth_api_version: str = "v1",
        auth_api_base_url: Optional[Union[str, URL]] = None,
        user_id_path_key: str = "user_id",
        http_client: Optional[httpx.AsyncClient] = None,
        **kwargs
    ):
        """
        初始化认证客户端。

        Args:
            homepage: 当前微服务的 Base URL。
            auth_homepage: 认证微服务主页 URL。
            auth_api_version: 认证微服务的版本，当未提供 `auth_api_base_url` 时有效。
            auth_api_base_url: 认证服务 API 的 Base URL。
            user_id_path_key: 路径中表示 user_id 的占位符名。
            http_client (httpx.AsyncClient): An HTTP client similar to `httpx.AsyncClient`, used for sending requests.
            kwargs: The initialization parameters passed to `http_client`.

        `auth_homepage` 与 `auth_api_base_url` 中至少提供一者。
            如果未提供 `auth_homepage`，则取 `auth_api_base_url` 的 `origin` 部分得到。
            如果未提供 `auth_api_base_url`，则拼接 `auth_homepage / "api" / auth_api_version`。
        """
        self.homepage: URL = URL(homepage)
        self.user_id_path_key = user_id_path_key

        # 认证微服务
        if not (auth_homepage or auth_api_base_url):
            raise ValueError("Provide at least one of `auth_home_page` and `auth_api_base_url`.")

        if auth_api_base_url:
            # 提供了 auth_api_base_url
            self.auth_api_base_url = URL(auth_api_base_url)
            # 如果未提供 auth_homepage，则从 api base 推导
            self.auth_homepage = URL(auth_homepage) if auth_homepage else self.auth_api_base_url.origin()
        else:
            # 仅提供了 auth_homepage
            self.auth_homepage = URL(auth_homepage)
            self.auth_api_base_url = self.auth_homepage / "api" / auth_api_version

        # HTTP Client
        headers = kwargs.setdefault("headers", {})
        if "user-agent" not in headers:
            headers["user-agent"] = UserAgent().random # 生成随机 UA
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


    def get_router(self, api_version: Optional[str] = None) -> APIRouter:
        """
        返回需要注册到根路由的 API URL。

        Args:
            api_version: 指定要注册的路由的版本。
                如果缺省，则全部注册。
        """
        if api_version is None:
            router = APIRouter()
            # 所有版本都注册
            for version in router_getters:
                router.include_router(self.get_router(version))
            return router

        # 检查版本的存在性
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
            UpstreamUnavailableException: 如果向认证微服务发送请求失败。
        """
        kwargs["url"] = str(self._get_auth_api_url(subpath))
        try:
            return await self._http_client.request(**kwargs)
        except Exception as error:
            raise UpstreamUnavailableException("认证服务不可用") from error


    def redirect_to_auth(
        self,
        current_path: str,
    ) -> None:
        """
        引发一个重定向到登录页面的 HTTPException。
        """
        redirect_url = self.homepage / current_path
        login_url = self.auth_homepage.with_query({"redirect": str(redirect_url)})
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": login_url},
        )


    # ==== FastAPI 依赖函数 ====

    async def get_current_account(
        self,
        request: Request,
        min_permission_level_high: Optional[int] = None,
    ) -> Account:
        """
        FastAPI 依赖函数，用于验证请求的登录态与权限等级。

        Args:
            request: FastAPI 请求对象
            min_permission_level: 大权限等级下限，用户等级需 >= 该值才可通过；为 None 时不校验权限

        Returns:
            含有当前登录态的 Account 对象。

        Raises:
            UpstreamUnavailableException: 认证服务不可用。
            HTTPException: 未登录时引发重定向；权限不足时返回 403。
        """
        account = Account(
            auth_client=self,
            cookies=request.cookies,
        )

        try:
            user_info = await account.get_user_info()

        except UnauthorizedException:
            # 未登录，重定向到认证主页
            current_url = URL(request.url)
            self.redirect_to_auth(current_url.path)

        if min_permission_level_high is None:
            # 不校验权限
            return account

        if (
            (user_info.permission_level_high is None) or
            (user_info.permission_level_high < min_permission_level_high)
        ):
            raise PermissionDeniedException()

        return account


    def get_current_account_dependence(
        self,
        min_permission_level_high: Optional[int] = None,
    ) -> Callable[[Request], Account]:
        """
        返回一个 FastAPI 的依赖函数，它的用法与 `.get_current_account` 相同，
        但是会额外要求当前用户的大权限等级不低于 `min_permission_level_high` 。
        """
        return partial(
            self.get_current_account,
            min_permission_level_high=min_permission_level_high
        )


    async def get_target_user(
        self,
        request: Request
    ) -> UserInfo:
        """
        FastAPI 依赖函数，根据路径中的动态参数名提取 user_id，并获取目标用户信息。

        用法示例（开发者使用时）：
            auth_client = AuthClient(..., user_id_path_key="custom_user_id")
            
            @app.get("/users/{custom_user_id}")
            async def get_user(
                current_account: Account = Depends(auth_client.get_current_account),
                target_user: UserInfo = Depends(auth_client.get_target_user)
            ):
                return {"target": target_user}

        Raises:
            UpstreamUnavailableException: 认证服务不可用。
            HTTPException: 未登录 / 登录已失效。重定向到登录页面。
            UserNotFoundException: 没有找到目标用户。
        """
        # 验证当前登录态
        current_account: Account = await self.get_current_account(request)

        # 从路径中提取 user_id
        user_id = request.path_params.get(self.user_id_path_key)
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"路径中缺少必需的参数: {self.user_id_path_key}"
            )

        # 用当前账号对象获取目标用户信息
        return current_account.get_user_info(user_id)


    async def get_manageable_target_user(
        self,
        request: Request
    ) -> UserInfo:
        """
        FastAPI 依赖函数，获取当前登录用户有权限管理的目标用户信息。

        适用于需要“用户管理”功能的端点（如修改、删除、查看其他用户详情），
        在获取目标用户的同时进行权限校验，确保操作合法。

        权限校验规则（按顺序）：
            1. 首先验证当前请求的登录态（通过 get_current_account），
               未登录会触发重定向到认证页。
            2. 从路径参数中提取目标用户 ID（键名由 self.user_id_path_key 指定）。
            3. 通过当前账号获取目标用户信息（调用 get_target_user）。
            4. 判断目标用户是否为当前登录用户自身：
                - 若是自身：允许访问（用户可管理自己的信息）。
                - 若不是自身：要求当前用户的“大权限等级”（permission_level_high）
                  **严格高于** 目标用户的“大权限等级”，否则抛出 PermissionDeniedException。

        典型用法（在路由中作为依赖注入）：
            auth_client = AuthClient(..., user_id_path_key="custom_user_id")

            @app.delete("/users/{custom_user_id}")
            async def delete_user(
                current_account: Account = Depends(auth_client.get_current_account),
                target_user: UserInfo = Depends(auth_client.get_manageable_target_user),
            ):
                # 此处 target_user 已经过权限校验，可直接执行删除逻辑
                await delete_user_by_id(target_user.id)
                return {"message": "用户已删除"}

        Raises:
            UnauthorizedException: 当前请求未登录（由 get_current_account 内部处理，
                实际会抛出 HTTP 302 重定向，不会直接抛出该异常）。
            HTTPException (400): 路径中缺少 user_id_path_key 指定的参数。
            PermissionDeniedException: 当前用户权限不足以管理目标用户（非自身且权限不够高）。
            UpstreamUnavailableException: 认证服务不可用（由内部调用引发）。
        """
        # 验证当前登录态
        current_account: Account = await self.get_current_account(request)
        # 获取目标用户信息（包含从路径提取 user_id）
        target_user: UserInfo = await self.get_target_user(request)
        # 获取当前用户自身信息
        current_user: UserInfo = await current_account.get_user_info()

        # 权限校验：非自身且权限不高则拒绝
        if target_user.id != current_user.id:
            if current_user.permission_level_high <= target_user.permission_level_high:
                raise PermissionDeniedException()

        return target_user
