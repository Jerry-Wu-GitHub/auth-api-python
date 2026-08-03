"""
Account
"""

from __future__ import annotations

from datetime import datetime
import json
from string import Template
from typing import Any, Dict, Optional, TYPE_CHECKING

import httpx
from starlette import status

from ..exceptions import (
    UpstreamException,
    UnauthorizedException,
    ResourceNotFoundException,
    UserNotFoundException,
    PermissionDeniedException,
    ParamValidationException,
)
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


    @staticmethod
    def _get_subpath(
        subpath_template: Template,
        *,
        user_id: Optional[str] = None,
        user_id_key: str = "user_id"
    ) -> str:
        """
        根据 user_id，返回要调用的 subpath。

        Args:
            subpath_template: subpath 模板，需要有名为 `user_id_key` 的占位符。
            user_id: 要插入到 subpath 中的 user_id。
                若缺省，则返回对应的 `/me` 版本。
            user_id_key: 在 `subpath_template` 中，要插入 `user_id` 的占位符名。

        Raises:
            TypeError: 如果 `user_id` 参数的类型不合法。
        """
        if user_id is None:
            return subpath_template.substitute({
                user_id_key: "me"
            })

        if isinstance(user_id, str):
            return subpath_template.substitute({
                user_id_key: user_id
            })

        raise TypeError(f"`user_id` excepts to be `str` object or `None`, but got `{user_id}`")



    async def request(self, **kwargs) -> httpx.Response:
        """
        合并参数，发送请求，返回响应对象。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            UpstreamException: 如果服务器响应内容不合法。
            UnauthorizedException: 如果 sid 无效，没有登录。
        """
        response = await self.auth_client.request(**kwargs)
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            raise UnauthorizedException()
        return response


    async def request_json(self, **kwargs) -> Dict[str, Any] | str | None:
        """
        合并参数，发送请求，返回响应体对象。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            UpstreamException: 如果服务器响应内容不合法。
            UnauthorizedException: 如果 sid 无效，没有登录。
            PermissionDeniedException: 如果权限不足。
            ResourceNotFoundException: 如果所访问的资源不存在。
            UserNotFoundException: 如果所访问的用户不存在。
            ParamValidationException: 如果提供的参数不合法。
        """
        kwargs = self._get_kwargs(kwargs)

        response = await self.request(**kwargs)
        if not response.text:
            return None

        try:
            resp_json = response.json()
        except json.JSONDecodeError as exp:
            raise UpstreamException(f"Unexcepted json string: {response.text}") from exp

        if not isinstance(resp_json, dict):
            return resp_json

        message = resp_json.get("message")

        if response.status_code == status.HTTP_403_FORBIDDEN:
            raise PermissionDeniedException(message)

        if response.status_code == status.HTTP_404_NOT_FOUND:
            code = resp_json.get("code")
            if code == "USER_NOT_FOUND":
                raise UserNotFoundException(message)
            raise ResourceNotFoundException(message)

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            raise ParamValidationException(message)

        response.raise_for_status()

        return resp_json


    # ==== /users ====

    async def get_user_info(self, user_id: Optional[str] = None, **kwargs) -> UserInfo:
        """
        获取用户基本信息。

        Args:
            user_id: 被查看的用户的 ID 。如果缺省，则查看自己的。
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Returns:
            UserInfo

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            UpstreamException: 如果对后端返回的内容解析失败。
        """
        kwargs["method"] = "GET"
        kwargs["subpath"] = self._get_subpath(
            Template("users/${user_id}"),
            user_id=user_id
        )

        resp_json = await self.request_json(**kwargs)

        try:
            resp_data = resp_json.get("data")
        except (json.JSONDecodeError, AttributeError) as error:
            raise UpstreamException(f"Unexcepted json structure: {resp_json}") from error

        if not (resp_data and isinstance(resp_data, dict)):
            raise UpstreamException(f"Data not found: {resp_json}")

        if not (
            (id_  := resp_data.get("userId")  ) and
            (name := resp_data.get("username"))
        ):
            raise UpstreamException(f"Unexcepted data structure: {resp_data}")

        created_at_str    = resp_data.get("createdAt")
        last_login_at_str = resp_data.get("lastLoginAt")

        try:
            created_at = datetime.fromisoformat(created_at_str) if created_at_str else None
            last_login_at = datetime.fromisoformat(last_login_at_str) if last_login_at_str else None
        except ValueError as error:
            raise UpstreamException(f"Unexcepted time format: {resp_data}") from error

        return UserInfo(
            id               = id_,
            name             = name,
            permission_level = resp_data.get("permissionLevel"),
            email            = resp_data.get("email"),
            created_at       = created_at,
            last_login_at    = last_login_at
        )


    async def update_user_info(
        self,
        username: Optional[str] = None,
        permission_level: Optional[int] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        更新用户名。

        Args:
            username: 新用户名，长度为 1~64。
            permission_level: 目标权限等级，0~255。
            user_id: 被修改的用户的 ID。缺省时，修改自己的用户名。
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            UpstreamException: 如果对后端返回的内容解析失败。
        """
        kwargs["method"] = "PATCH"
        kwargs["subpath"] = self._get_subpath(
            Template("users/${user_id}"),
            user_id=user_id
        )
        kwargs["json"] = {
            "username": username,
            "permissionLevel": permission_level,
        }

        await self.request_json(**kwargs)


    @staticmethod
    def _parse_preferences(resp_json: Dict[str, Any]) -> Preferences:
        try:
            resp_data = resp_json.get("data")
        except (json.JSONDecodeError, AttributeError) as error:
            raise UpstreamException(f"Unexcepted json string: {resp_json}") from error

        if not (resp_data and isinstance(resp_data, dict)):
            raise UpstreamException(f"Data not found: {resp_json}")

        if not (
            (theme        := resp_data.get("theme")      ) and
            (accent_color := resp_data.get("accentColor"))
        ):
            raise UpstreamException(f"Unexcepted data structure: {resp_data}")

        if not COLOR_PATTERN.fullmatch(accent_color):
            raise UpstreamException(f"Unexcepted color format: {accent_color}")

        return Preferences(
            theme=theme,
            accent_color=accent_color
        )


    async def get_preferences(
        self,
        user_id: Optional[str] = None,
        **kwargs
    ) -> Preferences:
        """
        获取用户偏好设置。

        Args:
            user_id: 被查看的用户的 ID。缺省时，查看自己的。
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Returns:
            Preference

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            UpstreamException: 如果对后端返回的内容解析失败。
        """
        kwargs["method"] = "GET"
        kwargs["subpath"] = self._get_subpath(
            Template("users/${user_id}/preferences"),
            user_id=user_id
        )

        resp_json = await self.request_json(**kwargs)

        return self._parse_preferences(resp_json)


    async def update_preferences(
        self,
        preference: Preferences,
        user_id: Optional[str] = None,
        **kwargs
    ) -> Preferences:
        """
        更新用户偏好设置。

        Args:
            preference: 偏好设置对象。
            user_id: 被修改的用户的 ID。缺省时，修改自己的用户名。
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            UpstreamException: 如果对后端返回的内容解析失败。

        Returns:
            Preferences: 修改后的用户偏好。
        """
        kwargs["method"] = "PATCH"
        kwargs["subpath"] = self._get_subpath(
            Template("users/${user_id}/preferences"),
            user_id=user_id
        )
        kwargs["json"] = {
            "theme": preference.theme,
            "accentColor": preference.accent_color
        }

        resp_json = await self.request_json(**kwargs)

        return self._parse_preferences(resp_json)


    # ==== /sessions ====

    async def logout(self, user_id: Optional[str] = None, **kwargs) -> None:
        """
        登出会话的登录。

        Args:
            user_id: 被登出的用户的 ID。
                若提供，则登出目标用户的所有会话。
                若缺省，则仅登出当前会话。
            kwargs: 传递给 auth_client.request 的其他参数，拥有最高优先级。

        Raises:
            AuthServerUnavailable: 如果向认证微服务发送请求失败。
            NotLoggedError: 如果 sid 无效，没有登录。
            UpstreamException: 如果对后端返回的内容解析失败。
        """
        kwargs["method"] = "DELETE"
        kwargs["subpath"] = self._get_subpath(
            Template("sessions/${user_id}"),
            user_id=user_id
        )

        await self.request_json(**kwargs)


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

        await self.request_json(**kwargs)
