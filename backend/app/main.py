"""
Application entrypoint. Run with:
    uvicorn app.main:app --reload --app-dir backend
(or `make dev` from the project root)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.exceptions import register_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.plugins.registry import bootstrap_registry

configure_logging()
logger = get_logger("jarvis.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("jarvis_starting", environment=settings.ENVIRONMENT)
    registry = bootstrap_registry()
    await registry.setup_all()
    logger.info("jarvis_ready", plugin_count=len(registry.list()))
    yield
    logger.info("jarvis_shutting_down")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Jarvis — an AI operating system for running the business.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
