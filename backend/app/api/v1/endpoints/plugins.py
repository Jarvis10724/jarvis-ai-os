from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.orchestrator import orchestrator
from app.db.models.plugin_config import PluginConfig
from app.db.session import get_db
from app.exceptions import AuthorizationError

router = APIRouter(prefix="/plugins", tags=["plugins"])


class RunPluginRequest(BaseModel):
    args: dict = {}


@router.get("")
def list_plugins(current_user: CurrentUser):
    return orchestrator.list_plugins()


@router.post("/{plugin_name}/run")
async def run_plugin(
    plugin_name: str,
    payload: RunPluginRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    # Settings > Plugins lets a user disable a plugin per-account. Enforce
    # that here — otherwise "Disabled" is cosmetic and Quick Actions/the
    # Plugins page can still run it.
    config = (
        db.query(PluginConfig)
        .filter(PluginConfig.owner_id == current_user.id, PluginConfig.plugin_name == plugin_name)
        .first()
    )
    if config is not None and not config.enabled:
        raise AuthorizationError(f"The '{plugin_name}' plugin is disabled in Settings.")

    result = await orchestrator.run_plugin(plugin_name, **payload.args)
    return {
        "success": result.success,
        "output": result.output,
        "message": result.message,
        "metadata": result.metadata,
    }
