"""
User
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic.dataclasses import dataclass
from pydantic import Field


@dataclass(frozen=True)
class UserInfo:
    """用户信息"""
    id: str = Field(
        description="用户在本站的唯一标识符（UUID）"
    )

    name: str = Field(
        description="用户名，1-64 字符"
    )

    email: Optional[str] = Field(
        description="用户的电子邮箱",
        default=None
    )

    created_at: datetime = Field(
        description="注册时间"
    )

    last_login_at: datetime = Field(
        description="最近一次登录时间"
    )


@dataclass(frozen=True)
class Preferences:
    """
    用户偏好设置。
    """
    theme: Literal["dark", "light", "system"] = Field(
        description="主题模式，可选 'dark', 'light', 'system'",
        default="system"
    )

    accent_color: str = Field(
        description="强调色，格式为 #rrggbb",
        default="#4a90d9"  # 默认蓝色调
    )


@dataclass(frozen=True)
class User:
    """用户实体"""
    info: UserInfo = Field(
        description="用户信息"
    )

    preferences: Preferences = Field(
        description="用户偏好",
        default_factory=Preferences
    )
