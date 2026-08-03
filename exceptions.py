"""
统一业务异常类。
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, Generic, Optional, TypeVar

from starlette import status


class BusinessException(Exception):
    """
    业务异常基类，所有业务错误都继承自这里。
    
    Attributes:
        code: 错误代码
        message: 错误消息
        details: 附加详情（可选）
    """

    # 默认响应码
    DEFAULT_STATUS_CODE : ClassVar[int] = status.HTTP_500_INTERNAL_SERVER_ERROR

    # 默认消息
    DEFAULT_MESSAGE     : ClassVar[str] = "Business Error"

    # 默认错误代码
    DEFAULT_CODE        : ClassVar[str] = "ERROR"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message    : str = self.DEFAULT_MESSAGE     if (message     is None) else message
        self.status_code: int = self.DEFAULT_STATUS_CODE if (status_code is None) else status_code
        self.code       : str = self.DEFAULT_CODE        if (code        is None) else code
        self.details    : Dict[str, Any] = details or {}

        super().__init__(self.message)


class UpstreamException(BusinessException):
    """
    上游服务出错
    """
    DEFAULT_STATUS_CODE = status.HTTP_502_BAD_GATEWAY
    DEFAULT_MESSAGE     = "Failed to call upstream service, upstream server returned an invalid response."
    DEFAULT_CODE        = "UPSTREAM_ERROR"


class UpstreamUnavailableException(UpstreamException):
    """
    无法访问上游服务
    """
    DEFAULT_MESSAGE     = "Failed to connect to upstream service."
    DEFAULT_CODE        = "UPSTREAM_UNAVAILABLE"


class UnauthorizedException(BusinessException):
    """
    未登录 / 认证失效
    """
    DEFAULT_STATUS_CODE = status.HTTP_401_UNAUTHORIZED
    DEFAULT_MESSAGE     = "You are not logged in, or your login session has expired."
    DEFAULT_CODE        = "UNAUTHORIZED"


class PermissionDeniedException(BusinessException):
    """
    无权限访问
    """
    DEFAULT_STATUS_CODE = status.HTTP_403_FORBIDDEN
    DEFAULT_MESSAGE     = "Your permissions are insufficient."
    DEFAULT_CODE        = "INSUFFICIENT_PERMISSIONS"


class ResourceNotFoundException(BusinessException):
    """
    资源不存在
    """
    DEFAULT_STATUS_CODE = status.HTTP_404_NOT_FOUND
    DEFAULT_MESSAGE     = "The requested resource does not exist."
    DEFAULT_CODE        = "RESOURCE_NOT_FOUND"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        if resource_id is not None:
            details = details or {}
            details["resource_id"] = resource_id
        super().__init__(
            message=message,
            details=details,
            **kwargs
        )


class OAuthProviderNotFoundException(ResourceNotFoundException):
    """
    第三方认证平台不存在
    """
    DEFAULT_MESSAGE     = "The login method does not exist."
    DEFAULT_CODE        = "OAUTH_PROVIDER_NOT_FOUND"


class UserNotFoundException(ResourceNotFoundException):
    """
    用户不存在
    """
    DEFAULT_MESSAGE     = "The user does not exist or has been deleted."
    DEFAULT_CODE        = "USER_NOT_FOUND"


ParamType = TypeVar("ParamType")

class ParamValidationException(BusinessException, Generic[ParamType]):
    """
    参数校验失败
    """
    DEFAULT_STATUS_CODE = status.HTTP_400_BAD_REQUEST
    DEFAULT_MESSAGE     = "Parameter verification failed."
    DEFAULT_CODE        = "INVALID_PARAMETER"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        provided: Optional[ParamType] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        if provided is not None:
            details = details or {}
            details["provided"] = provided
        super().__init__(
            message=message,
            details=details,
            **kwargs
        )


class InvalidRedirectUriException(BusinessException):
    """
    回调地址域名不在白名单中
    """
    DEFAULT_STATUS_CODE = status.HTTP_422_UNPROCESSABLE_ENTITY
    DEFAULT_MESSAGE = "The redirect URI domain is not in the whitelist."
    DEFAULT_CODE = "REDIRECT_URI_NOT_ALLOWED"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        domain: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Args:
            domain: the domain part of the redirect uri.
        """
        if domain is not None:
            details = details or {}
            details["domain"] = domain
        super().__init__(
            message=message,
            details=details,
            **kwargs
        )
