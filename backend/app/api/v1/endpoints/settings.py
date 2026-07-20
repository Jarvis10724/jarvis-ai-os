"""
Per-user application settings — currently plugin enable/disable + config.
Distinct from app.config.Settings, which is process-wide, not per-user.
"""
import json

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.models.plugin_config import PluginConfig
from app.db.session import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


class PluginConfigRead(BaseModel):
    plugin_name: str
    enabled: bool
    config: dict

    model_config = {"from_attributes": True}


class PluginConfigUpdate(BaseModel):
    enabled: bool | None = None
    config: dict | None = None


@router.get("/plugins", response_model=list[PluginConfigRead])
def list_plugin_settings(current_user: CurrentUser, db: Session = Depends(get_db)):
    rows = db.query(PluginConfig).filter(PluginConfig.owner_id == current_user.id).all()
    return [
        PluginConfigRead(
            plugin_name=r.plugin_name,
            enabled=r.enabled,
            config=json.loads(r.config_json) if r.config_json else {},
        )
        for r in rows
    ]


@router.put("/plugins/{plugin_name}", response_model=PluginConfigRead)
def update_plugin_settings(
    plugin_name: str,
    payload: PluginConfigUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    row = (
        db.query(PluginConfig)
        .filter(PluginConfig.owner_id == current_user.id, PluginConfig.plugin_name == plugin_name)
        .first()
    )
    if not row:
        row = PluginConfig(owner_id=current_user.id, plugin_name=plugin_name, enabled=True)
        db.add(row)

    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.config is not None:
        row.config_json = json.dumps(payload.config)

    db.commit()
    db.refresh(row)
    return PluginConfigRead(
        plugin_name=row.plugin_name,
        enabled=row.enabled,
        config=json.loads(row.config_json) if row.config_json else {},
    )
