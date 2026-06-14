from typing import Optional, Any, Dict
from schemas import ApiResponse


def build_response(code: int, message: str, data: Optional[Any] = None) -> ApiResponse:
    return ApiResponse(code=code, message=message, data=data)


def success_response(message: str = "success", data: Optional[Any] = None) -> ApiResponse:
    return build_response(200, message, data)


def error_response(code: int, message: str, data: Optional[Any] = None) -> ApiResponse:
    return build_response(code, message, data)


def bad_request_response(message: str, data: Optional[Any] = None) -> ApiResponse:
    return build_response(400, message, data)


def not_found_response(message: str, data: Optional[Any] = None) -> ApiResponse:
    return build_response(404, message, data)


def wrap_with_response(result: Any, message: str = "操作成功") -> ApiResponse:
    if result is None:
        return not_found_response("数据不存在")
    return success_response(message, result)
