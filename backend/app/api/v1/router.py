from fastapi import APIRouter

from app.api.v1.endpoints import (
    agents,
    brand_brain,
    calendar,
    capabilities,
    chat,
    clients,
    command_center,
    company,
    dashboard,
    drive,
    gmail,
    health,
    integrations,
    market,
    memory,
    plugins,
    projects,
    settings,
    shopify,
    sync,
    tasks,
    work_queue,
    workspace_import,
    workspace_intelligence,
    workspaces,
)
from app.auth.router import router as auth_router

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(sync.router)
api_router.include_router(auth_router)
api_router.include_router(chat.router)
api_router.include_router(plugins.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(workspaces.router)
api_router.include_router(agents.router)
api_router.include_router(clients.router)
api_router.include_router(company.router)
api_router.include_router(integrations.router)
api_router.include_router(settings.router)
api_router.include_router(memory.router)
api_router.include_router(market.router)
api_router.include_router(capabilities.capabilities_router)
api_router.include_router(capabilities.approvals_router)
api_router.include_router(capabilities.scheduled_jobs_router)
api_router.include_router(gmail.router)
api_router.include_router(calendar.router)
api_router.include_router(drive.router)
api_router.include_router(dashboard.router)
api_router.include_router(shopify.router)
api_router.include_router(brand_brain.router)
api_router.include_router(work_queue.router)
api_router.include_router(command_center.router)
api_router.include_router(workspace_intelligence.router)
api_router.include_router(workspace_import.router)
