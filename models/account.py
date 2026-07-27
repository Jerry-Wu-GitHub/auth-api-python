"""
Account
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, Optional, TYPE_CHECKING

import httpx
from starlette import status

from ..config import SESSION_COOKIE_NAME
from ..exceptions import AuthServerError, NotLoggedError
from .user import UserInfo, Preferences
from ..utils.regex import COLOR_PATTERN

if TYPE_CHECKING:
    from .auth_client import AuthClient


class Account:
    """
    账户类。

    提供对账户的操作。
    """

    def __init__(
        self,
        auth_client: AuthClient,
        **kwargs
    ):
        """
        Args:
            auth_client: 用于向认证微服务发送网络请求。
            kwargs: 传递给 auth_client.request 的其他参数
        """
        self.auth_client = auth_client
        self._kwargs = kwargs


    def _get_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并发送请求的参数。
        """
        return self._kwargs | kwargs


    async def request(self, **kwargs) -> httpx.Response:
        """
        合并参数，发送请求，抛出 401 未登录错误。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
        """
        kwargs = self._get_kwargs(kwargs)
        response = await self.auth_client.request(**kwargs)
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            raise NotLoggedError("Unauthorized")
        return response


    # ==== /users ====

    async def get_info(self, **kwargs) -> UserInfo:
        """
        获取用户基本信息。

        Args:
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Returns:
            UserInfo

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            AuthServerError: 如果对后端返回的内容解析失败。
        """
        kwargs["method"] = "GET"
        kwargs["subpath"] = "users/me"

        response = await self.request(**kwargs)
        response.raise_for_status()

        try:
            resp_json = response.json()
            resp_data = resp_json.get("data")
        except (json.decoder.JSONDecodeError, AttributeError) as error:
            raise AuthServerError(f"Unexcepted json string: {response.text}") from error

        if not (resp_data and isinstance(resp_data, dict)):
            raise AuthServerError(f"Data not found: {resp_json}")

        if not (
            (id_               := resp_data.get("userId")           ) and
            (name              := resp_data.get("username")         ) and
            (created_at_str    := resp_data.get("createdAt")    ) and
            (last_login_at_str := resp_data.get("lastLoginTime"))
        ):
            raise AuthServerError(f"Unexcepted data structure: {resp_data}")

        try:
            created_at = datetime.fromisoformat(created_at_str)
            last_login_at = datetime.fromisoformat(last_login_at_str)
        except ValueError as error:
            raise AuthServerError(f"Unexcepted time format: {resp_data}") from error

        return UserInfo(
            id            = id_,
            name          = name,
            email         = resp_data.get("email"),
            created_at    = created_at,
            last_login_at = last_login_at
        )


    async def update_username(self, username: str, **kwargs) -> None:
        """
        更新用户名。

        Args:
            username: 新用户名
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            AuthServerError: 如果对后端返回的内容解析失败。
        """
        kwargs["method"] = "PATCH"
        kwargs["subpath"] = "users/me"
        kwargs["json"] = {"username": username}

        response = await self.request(**kwargs)
        response.raise_for_status()


    async def get_preferences(self, **kwargs) -> Preferences:
        """
        获取用户偏好设置。

        Args:
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Returns:
            Preference

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            AuthServerError: 如果对后端返回的内容解析失败。
        """
        kwargs["method"] = "GET"
        kwargs["subpath"] = "users/me/preferences"

        response = await self.request(**kwargs)
        response.raise_for_status()

        try:
            resp_json = response.json()
            resp_data = resp_json.get("data")
        except (json.decoder.JSONDecodeError, AttributeError) as error:
            raise AuthServerError(f"Unexcepted json string: {response.text}") from error

        if not (resp_data and isinstance(resp_data, dict)):
            raise AuthServerError(f"Data not found: {resp_json}")

        if not (
            (theme        := resp_data.get("theme")      ) and
            (accent_color := resp_data.get("accentColor"))
        ):
            raise AuthServerError(f"Unexcepted data structure: {resp_data}")

        if not COLOR_PATTERN.fullmatch(accent_color):
            raise AuthServerError(f"Unexcepted color format: {accent_color}")

        return Preferences(
            theme=theme,
            accent_color=accent_color
        )


    async def update_preferences(self, preference: Preferences, **kwargs) -> None:
        """
        更新用户偏好设置。

        Args:
            preference: 偏好设置对象
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            AuthServerError: 如果对后端返回的内容解析失败。
        """
        kwargs["method"] = "PATCH"
        kwargs["subpath"] = "users/me/preferences"
        kwargs["json"] = {
            "theme": preference.theme,
            "accentColor": preference.accent_color
        }

        response = await self.request(**kwargs)
        response.raise_for_status()


    # ==== /sessions ====

    async def logout(self, **kwargs) -> None:
        """
        登出当前会话。

        Args:
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            AuthServerError: 如果对后端返回的内容解析失败。
        """
        kwargs["method"] = "DELETE"
        kwargs["subpath"] = "sessions/me"

        response = await self.request(**kwargs)
        response.raise_for_status()


    async def keep_alive(self, **kwargs) -> None:
        """
        刷新会话有效期。

        Args:
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
        """
        kwargs["method"] = "PATCH"
        kwargs["subpath"] = "sessions/me"

        response = await self.request(**kwargs)
        response.raise_for_status()
