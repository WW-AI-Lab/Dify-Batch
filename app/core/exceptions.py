"""
自定义异常类和异常处理
"""
from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseCustomException(Exception):
    """自定义异常基类"""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class DifyAPIException(BaseCustomException):
    """Dify API相关异常"""
    
    def __init__(self, message: str, status_code: int = status.HTTP_502_BAD_GATEWAY, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)


class FileProcessingException(BaseCustomException):
    """文件处理异常"""
    
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)


class TaskExecutionException(BaseCustomException):
    """任务执行异常"""
    
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)


class ValidationException(BaseCustomException):
    """数据验证异常"""
    
    def __init__(self, message: str, status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)


class DatabaseException(BaseCustomException):
    """数据库操作异常"""
    
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)


class AuthenticationException(BaseCustomException):
    """认证异常"""
    
    def __init__(self, message: str = "认证失败", status_code: int = status.HTTP_401_UNAUTHORIZED, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)


class AuthorizationException(BaseCustomException):
    """授权异常"""
    
    def __init__(self, message: str = "权限不足", status_code: int = status.HTTP_403_FORBIDDEN, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)


class ResourceNotFoundException(BaseCustomException):
    """资源未找到异常"""
    
    def __init__(self, message: str = "资源未找到", status_code: int = status.HTTP_404_NOT_FOUND, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)


class RateLimitException(BaseCustomException):
    """限流异常"""
    
    def __init__(self, message: str = "请求过于频繁", status_code: int = status.HTTP_429_TOO_MANY_REQUESTS, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)


async def custom_exception_handler(request: Request, exc: BaseCustomException) -> JSONResponse:
    """自定义异常处理器"""
    logger.error(f"自定义异常: {exc.message}", extra={
        "status_code": exc.status_code,
        "details": exc.details,
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
            "details": exc.details,
            "path": request.url.path,
            "timestamp": logger._core.now().isoformat()
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP异常处理器"""
    logger.warning(f"HTTP异常: {exc.detail}", extra={
        "status_code": exc.status_code,
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "path": request.url.path,
            "timestamp": logger._core.now().isoformat()
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器"""
    logger.exception(f"未处理的异常: {str(exc)}", extra={
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "服务器内部错误",
            "path": request.url.path,
            "timestamp": logger._core.now().isoformat()
        }
    ) 