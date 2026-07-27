"""
/api/v1 的子路由的公共常量。
"""

from ....config import CONFIRMATION_API_NAME


API_VERSION = "v1"
API_PREFIX = f"api/{API_VERSION}"

# Set-Cookie 接口的 Path
CONFIRMATION_API_PATH: str = f"{API_PREFIX}/sessions/{CONFIRMATION_API_NAME}"
