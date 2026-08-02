"""
异常。
"""

class AuthError(Exception):
    """与认证相关的错误"""


class AuthServerError(AuthError):
    """上游的认证微服务出错"""


class AuthServerUnavailable(AuthError):
    """无法访问认证微服务"""


class UnauthorizedException(AuthError):
    """未登录 / 认证失效"""


class PermissionDeniedException(AuthError):
    """无权限访问"""


class ResourceNotFoundException(AuthError):
    """资源不存在"""


class UserNotFoundException(ResourceNotFoundException):
    """用户不存在"""


class ParamValidationException(AuthError):
    """参数校验失败"""
