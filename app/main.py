from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import time
import os

from app.config import get_settings
from app.core.constants import API_VERSION, API_PREFIX
from app.core.exceptions import MarketDataException
from app.core.logging_config import configure_logging, logger
from app.core.metrics import APP_INFO, REQUEST_COUNT, REQUEST_LATENCY
from app.services.database import init_db
from app.services.cache import cache_service
from app.adapters.factory import AdapterFactory
from app.api.v1.router import api_router
from app.api.v1.websockets.ohlc import router as ws_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_startup", version=API_VERSION)

    APP_INFO.info({"version": API_VERSION, "environment": settings.environment})

    configure_logging(settings.log_level)

    try:
        init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_init_failed", error=str(e))

    AdapterFactory.get_adapters()

    from app.etl.scheduler import scheduler

    await scheduler.start(interval_seconds=300)
    logger.info("etl_scheduler_started", interval=300)

    yield

    await scheduler.stop()
    await cache_service.close()
    await AdapterFactory.close_all()

    logger.info("application_shutdown")


app = FastAPI(
    title="Market Data Platform",
    description="Real-time Index Data Aggregation & Distribution System",
    version=API_VERSION,
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(MarketDataException)
async def market_data_exception_handler(request: Request, exc: MarketDataException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code.value,
                "message": exc.message,
                "details": exc.details,
                "path": str(request.url),
            }
        },
    )


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    REQUEST_COUNT.labels(
        method=request.method, endpoint=request.url.path, status=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(duration)

    return response


app.include_router(api_router, prefix=API_PREFIX)
app.include_router(ws_router)


frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/")
async def root():
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"name": "Market Data Platform", "version": API_VERSION, "docs": f"{API_PREFIX}/docs"}


@app.get("/metrics")
async def metrics():
    from fastapi.responses import Response

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
