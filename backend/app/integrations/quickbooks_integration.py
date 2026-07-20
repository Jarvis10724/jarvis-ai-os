"""
QuickBooks Online integration — invoices, expenses, reports.

STATUS: stub. QuickBooks uses Intuit's OAuth2 (see
https://developer.intuit.com/app/developer/qbo/docs/get-started). Needs a
company/realm id alongside the token, stored in extra_json on
IntegrationCredential.
"""
from app.config import settings
from app.exceptions import IntegrationError
from app.integrations.base import BaseIntegration, IntegrationActionResult

QBO_SCOPES = ["com.intuit.quickbooks.accounting"]


class QuickBooksIntegration(BaseIntegration):
    name = "quickbooks"
    description = "Read/write invoices, expenses, and reports in QuickBooks Online."

    async def is_connected(self) -> bool:
        return bool(self.credentials.get("access_token")) and bool(
            self.credentials.get("extra_json", {}).get("realm_id")
            if isinstance(self.credentials.get("extra_json"), dict)
            else False
        )

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        if not settings.QUICKBOOKS_CLIENT_ID:
            raise IntegrationError("QUICKBOOKS_CLIENT_ID is not configured")
        scope = "%20".join(QBO_SCOPES)
        return (
            "https://appcenter.intuit.com/connect/oauth2"
            f"?client_id={settings.QUICKBOOKS_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code&scope={scope}&state={state}"
        )

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        # TODO: POST to https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer
        # Also capture the `realmId` query param Intuit sends back on the
        # callback — that's the company id, store it in extra_json.
        raise NotImplementedError("QuickBooks token exchange not yet implemented")

    async def list_invoices(self, limit: int = 20) -> IntegrationActionResult:
        # TODO: call the QBO Query endpoint: SELECT * FROM Invoice.
        raise NotImplementedError("list_invoices not yet implemented")

    async def create_invoice(self, customer_id: str, line_items: list[dict]) -> IntegrationActionResult:
        # TODO: POST to the QBO Invoice endpoint.
        raise NotImplementedError("create_invoice not yet implemented")
