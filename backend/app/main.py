import redis as redis_lib
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.api.endpoints import alerts
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import setup_logging
from app.api.router import api_router

settings = get_settings()
setup_logging()

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title="FilamentFinder API",
    description="Price tracking system for 3D printing consumables",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "errors": [],
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {
            "field": ".".join(str(loc) for loc in err.get("loc", [])),
            "message": err.get("msg", ""),
            "code": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "status_code": 422,
            "errors": errors,
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_origin_regex=r"^chrome-extension://.*$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])


@app.get("/health")
def health_check():
    checks = {"database": "ok", "redis": "ok"}
    healthy = True

    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as exc:
        checks["database"] = str(exc)
        healthy = False

    try:
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        r.close()
    except Exception as exc:
        checks["redis"] = str(exc)
        healthy = False

    status_code = 200 if healthy else 503
    return JSONResponse(
        content={"status": "healthy" if healthy else "unhealthy", "checks": checks},
        status_code=status_code,
    )


@app.get("/")
def root():
    return {
        "name": "FilamentFinder API",
        "version": "1.0.0",
        "docs": "/docs",
    }
