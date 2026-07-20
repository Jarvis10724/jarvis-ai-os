"""
Integration discovery and lookup — mirrors app/plugins/registry.py.
"""
from app.exceptions import IntegrationError
from app.integrations.amazon_integration import AmazonIntegration
from app.integrations.base import BaseIntegration
from app.integrations.email_integration import EmailIntegration
from app.integrations.google_calendar_integration import GoogleCalendarIntegration
from app.integrations.google_drive_integration import GoogleDriveIntegration
from app.integrations.quickbooks_integration import QuickBooksIntegration
from app.integrations.shopify_integration import ShopifyIntegration
from app.integrations.social_media_integration import (
    FacebookIntegration,
    InstagramIntegration,
    LinkedInIntegration,
    TwitterIntegration,
)

INTEGRATION_CLASSES: dict[str, type[BaseIntegration]] = {
    cls.name: cls
    for cls in [
        EmailIntegration,
        GoogleCalendarIntegration,
        GoogleDriveIntegration,
        QuickBooksIntegration,
        AmazonIntegration,
        ShopifyIntegration,
        TwitterIntegration,
        LinkedInIntegration,
        FacebookIntegration,
        InstagramIntegration,
    ]
}


def get_integration(name: str, credentials: dict | None = None) -> BaseIntegration:
    if name not in INTEGRATION_CLASSES:
        raise IntegrationError(
            f"Unknown integration '{name}'. Available: {list(INTEGRATION_CLASSES)}"
        )
    return INTEGRATION_CLASSES[name](credentials=credentials)


def list_integrations() -> list[dict]:
    return [
        {"name": cls.name, "description": cls.description}
        for cls in INTEGRATION_CLASSES.values()
    ]
