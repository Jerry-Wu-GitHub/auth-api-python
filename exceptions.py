"""
异常。
"""

class AuthError(Exception):
    """与认证相关的错误"""


class AuthServerError(AuthError):
    """上游的认证微服务出错"""


class AuthServerUnavailable(AuthError):
    """无法访问认证微服务"""


class NotLoggedError(AuthError):
    """未登录"""
