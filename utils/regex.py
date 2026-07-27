"""
正则表达式
"""

import re

# 颜色格式正则
COLOR_PATTERN: re.Pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
