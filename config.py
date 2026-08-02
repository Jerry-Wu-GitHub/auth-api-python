from typing import Dict

# Cookie 的默认过期时间
COOKIE_MAX_AGE = 604800

# Set-Cookie 接口的端点名
CONFIRMATION_API_NAME = "confirmation"

# 用户名限制
USERNAME_LENGTH_MIN: int = 1
USERNAME_LENGTH_MAX: int = 64

# 用户权限等级的范围
PERMISSION_LEVEL_MIN: int = 0x00
PERMISSION_LEVEL_MAX: int = 0xFF
DEFAULT_PERMISSION_LEVEL: int = 0x01

# 颜色格式
COLOR_PATTERN_STR: str = r"^#[0-9a-fA-F]{6}$"

# 用户偏好默认值
DEFAULT_PREFERENCES: Dict[str, str] = {
    "theme": "system",
    "accent_color": "#4a90d9", # 默认蓝色调
}
