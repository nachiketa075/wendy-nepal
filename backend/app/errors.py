from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """Error returned to clients as {"error": {"code", "message", "fields"}}."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields or {}
        self.headers = headers


def _body(code: str, message: str, fields: dict[str, str] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "fields": fields or {}}}


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(_body(exc.code, exc.message, exc.fields), status_code=exc.status_code, headers=exc.headers)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
        name = ".".join(loc) or "request"
        message = err["msg"].removeprefix("Value error, ")
        if err["type"] == "extra_forbidden":
            message = "This field is not accepted."
        fields.setdefault(name, message)
    return JSONResponse(_body("validation_error", "Please check the highlighted details.", fields), status_code=422)


async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(_body("http_error", str(exc.detail)), status_code=exc.status_code, headers=exc.headers)
