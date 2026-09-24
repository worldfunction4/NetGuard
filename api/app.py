"""创建 FastAPI 应用，挂上设备与任务路由，并把异常收成统一 JSON。"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as ModelValidationError
from starlette.exceptions import HTTPException

from api.devices import router as devices_router
from api.jobs import router as jobs_router
from api.schemas import ErrorDetail, ErrorResponse
from logger import setup_logger

logger = setup_logger()

# 只暴露业务接口，不挂文档页。
app = FastAPI(
    title="NetGuard",
    description="网络设备备份、巡检和对比",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(devices_router)
app.include_router(jobs_router)


def _error(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status, content=body.model_dump())


def _validation_message(exc: RequestValidationError) -> str:
    """拼校验说明。不读取 input / body，避免把密码原文写进响应。"""
    parts: list[str] = []
    for err in exc.errors():
        if not isinstance(err, dict):
            continue
        loc = [str(item) for item in err.get("loc", ()) if str(item) != "body"]
        field = ".".join(loc) if loc else "请求体"
        if field == "password" or field.endswith(".password"):
            parts.append("password: 不合法")
            continue
        msg = str(err.get("msg", "不合法"))
        prefix = "Value error, "
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
        if len(msg) > 300:
            msg = msg[:300]
        parts.append(f"{field}: {msg}")
    return "；".join(parts) if parts else "请求体不合法"


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # 不记录 exc，它的文本里可能含有请求体。
    return _error(400, "VALIDATION_ERROR", _validation_message(exc))


@app.exception_handler(ModelValidationError)
async def model_validation_handler(
    request: Request, exc: ModelValidationError
) -> JSONResponse:
    # Pydantic 的校验异常文本会带上输入值，不能写进日志或响应。
    logger.error(
        "模型校验异常 %s %s",
        request.method,
        request.url.path,
    )
    return _error(500, "INTERNAL_ERROR", "服务器内部错误")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return _error(400, "VALIDATION_ERROR", str(exc))


@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    # 找不到设备时文案里带「不存在」，仍按资源不存在返回整句。
    # 字典缺键时 args 往往只是字段名，不能当成 404，也不能只回字段名。
    text = exc.args[0] if exc.args and isinstance(exc.args[0], str) else ""
    if "不存在" in text:
        return _error(404, "NOT_FOUND", text)
    if text:
        message = f"设备数据缺少 '{text}' 字段"
    else:
        message = "设备数据缺少必要字段"
    return _error(400, "VALIDATION_ERROR", message)


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(
    request: Request, exc: FileNotFoundError
) -> JSONResponse:
    return _error(404, "NOT_FOUND", str(exc))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 404:
        code = "NOT_FOUND"
        message = "资源不存在"
    elif exc.status_code in (400, 422):
        code = "VALIDATION_ERROR"
        message = exc.detail if isinstance(exc.detail, str) else "请求不合法"
    else:
        code = "HTTP_ERROR"
        message = exc.detail if isinstance(exc.detail, str) else "请求无法处理"
    return _error(exc.status_code, code, message)


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # 只记异常类型，不记异常文本，避免连接失败信息里夹带密码。
    logger.error(
        "未处理异常 %s %s %s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return _error(500, "INTERNAL_ERROR", "服务器内部错误")
