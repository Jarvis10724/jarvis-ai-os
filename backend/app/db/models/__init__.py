"""
Import every model here so Base.metadata is fully populated for Alembic
autogenerate and for `Base.metadata.create_all()` in tests/dev bootstrap.
"""
from app.db.models.agent_run import AgentRun
from app.db.models.capability import (
    ApprovalRequest,
    CapabilityAuditLog,
    CapabilityConfig,
    ScheduledJob,
)
from app.db.models.client import Client
from app.db.models.company import Company, Product
from app.db.models.integration_credential import IntegrationCredential
from app.db.models.memory import MemoryAuditLog, MemoryEntry, MemoryLink
from app.db.models.oauth_state import OAuthState
from app.db.models.plugin_config import PluginConfig
from app.db.models.project import Project
from app.db.models.project_event import ProjectEvent
from app.db.models.task import Task
from app.db.models.user import User
from app.db.models.workspace_session import WorkspaceSession

__all__ = [
    "User",
    "Project",
    "ProjectEvent",
    "Task",
    "WorkspaceSession",
    "PluginConfig",
    "IntegrationCredential",
    "Client",
    "Company",
    "Product",
    "MemoryEntry",
    "MemoryLink",
    "MemoryAuditLog",
    "CapabilityConfig",
    "ApprovalRequest",
    "CapabilityAuditLog",
    "ScheduledJob",
    "OAuthState",
    "AgentRun",
]
