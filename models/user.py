"""
User
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic.dataclasses import dataclass
from pydantic import Field

from ..config import (
    USERNAME_LENGTH_MIN, USERNAME_LENGTH_MAX,
    PERMISSION_LEVEL_MIN, PERMISSION_LEVEL_MAX,
    COLOR_PATTERN_STR, DEFAULT_PREFERENCES,
)


@dataclass(frozen=True)
class UserInfo:
    """用户信息"""
    id: str = Field(
        description="用户在本站的唯一标识符（UUID）"
    )

    name: str = Field(
        min_length=USERNAME_LENGTH_MIN,
        max_length=USERNAME_LENGTH_MAX,
        description=f"用户名，{USERNAME_LENGTH_MIN} ~ {USERNAME_LENGTH_MAX} 字符。"
    )

    permission_level: Optional[int] = Field(
        ge=PERMISSION_LEVEL_MIN,
        le=PERMISSION_LEVEL_MAX,
        description=f"权限等级，范围为 {PERMISSION_LEVEL_MIN} ~ {PERMISSION_LEVEL_MAX}。值越大，权限越大。",
        default=None
    )

    email: Optional[str] = Field(
        description="用户的电子邮箱",
        default=None
    )

    created_at: Optional[datetime] = Field(
        description="注册时间",
        default=None
    )

    last_login_at: Optional[datetime] = Field(
        description="最近一次登录时间",
        default=None
    )


@dataclass(frozen=True)
class Preferences:
    """
    用户偏好设置。
    """
    theme: Literal["dark", "light", "system"] = Field(
        description="主题模式，可选 'dark', 'light', 'system'",
        default=DEFAULT_PREFERENCES["theme"]
    )

    accent_color: str = Field(
        description="强调色，格式为 #rrggbb",
        pattern=COLOR_PATTERN_STR,
        default=DEFAULT_PREFERENCES["accent_color"]
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
