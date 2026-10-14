import logging
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .errors import ApiError, api_error_handler, http_error_handler, validation_error_handler
from .routers import auth, customer, inventory, owner, public, staff
from .safe_logging import log_unexpected, new_error_id
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


def _server_error(request: Request, exc: Exception) -> JSONResponse:
    """Record an unexpected error safely and answer with a generic message.

    The log line carries a reference id, the exception type and where it was
    raised, but never the exception text (see app/safe_logging.py). The same id
    is returned to the client so a report can be matched to the log.
    """
    error_id = new_error_id()
    route = request.scope.get("route")
    log_unexpected(exc, error_id, request.method, getattr(route, "path", "(unmatched)"))
    return JSONResponse(
        {"error": {"code": "server_error", "message": "Something went wrong on our side. Please try again.",
                   "fields": {}, "reference": error_id}},
        status_code=500,
        headers={"Cache-Control": "no-store"},
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
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        # Handled here, not by a catch-all exception handler: Starlette would
        # re-raise after such a handler and the server would then log the full
        # exception text, which can contain customer data.
        return _server_error(request, exc)
    # API answers can hold personal data; never let a browser or proxy store
    # them, except the two public read-only resources.
    if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
        public = request.method == "GET" and request.url.path in ("/api/menu", "/api/booking/config")
        response.headers["Cache-Control"] = "public, max-age=60" if public else "no-store"
    return response


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
app.include_router(inventory.router)
app.include_router(owner.router)
