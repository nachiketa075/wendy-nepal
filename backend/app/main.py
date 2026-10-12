import logging
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .errors import ApiError, api_error_handler, http_error_handler, validation_error_handler
from .routers import auth, customer, owner, public, staff
from .security import SAFE_METHODS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = get_settings()

app = FastAPI(
    title="Wendy Juice Shop API",
    docs_url=None if settings.environment == "production" else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.environment == "production" else "/api/openapi.json",
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    # Details go to the server log only; clients never see a stack trace.
    logging.getLogger("wendy").exception("unhandled error")
    return JSONResponse(
        {"error": {"code": "server_error", "message": "Something went wrong on our side. Please try again.", "fields": {}}},
        status_code=500,
    )


@app.middleware("http")
async def reject_cross_site_writes(request: Request, call_next):
    """Refuse state-changing requests whose Origin is neither this host nor an
    allowed origin. Complements the SameSite cookie and the CSRF token."""
    origin = request.headers.get("origin")
    if request.method not in SAFE_METHODS and origin:
        same_host = urlsplit(origin).netloc == request.headers.get("host")
        if not same_host and origin.rstrip("/") not in settings.cors_origin_list:
            return JSONResponse(
                {"error": {"code": "bad_origin", "message": "Request origin is not allowed.", "fields": {}}},
                status_code=403,
            )
    return await call_next(request)


if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(customer.router)
app.include_router(staff.router)
app.include_router(owner.router)
