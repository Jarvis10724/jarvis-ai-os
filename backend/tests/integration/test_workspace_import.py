"""
Workspace import — filling a workspace from its connected sources.

The classification and relevance rules are pure functions, so they're tested
directly: they decide what lands in a business knowledge base, and getting them
wrong is worse than importing nothing. The first live run proved that — it read
"sign" inside "sign-in" and turned every login alert into a signature request,
and it filed Shopify marketing as business information.
"""
from app.core.workspace_import_service import (
    classify_section,
    doc_kind,
    flag_attention,
    is_relevant_email,
)

API = "/api/v1"


# --- Filing --------------------------------------------------------------


def test_items_file_under_the_section_they_belong_to():
    assert classify_section("JAR LABELS _ 5X.75_", "application/pdf") == "packaging"
    assert classify_section("PUMP BOTTLE _ 5X2.5_") == "packaging"
    assert classify_section("Fonts", "application/vnd.google-apps.folder") == "brand"
    assert classify_section("Marketing _ Social + Email") == "marketing"
    assert classify_section("Quote from the filler for the 4oz batch") == "manufacturing"
    assert classify_section("Supplier COA — batch 22") == "manufacturing"
    # Nothing recognisable is filed as a document rather than guessed at.
    assert classify_section("Scan_20260714.pdf") == "documents"


def test_document_kinds_are_named_from_the_mime_type():
    assert doc_kind("application/pdf") == "PDF"
    assert doc_kind("application/vnd.google-apps.spreadsheet") == "Spreadsheet"
    assert doc_kind("image/png") == "Image"
    assert doc_kind("application/vnd.google-apps.folder") == "Folder"
    assert doc_kind(None) == "File"


# --- What counts as needing attention ------------------------------------


def test_a_login_alert_is_not_a_signature_request():
    """The exact false positive from the first live run."""
    assert flag_attention("New sign-in to your Shopify account") is None
    assert flag_attention("Someone signed in to your account") is None


def test_real_attention_items_are_still_flagged():
    assert flag_attention("Please sign the supplier agreement") == "signature"
    assert flag_attention("Invoice 8842 attached") == "payment"
    assert flag_attention("Quote for 5,000 jars") == "quote"
    assert flag_attention("Your shipment is delayed at customs") == "shipment"
    assert flag_attention("Action required before Friday") == "urgent"


# --- What counts as business information ----------------------------------


def test_platform_chatter_is_not_imported_as_business_information():
    assert not is_relevant_email("Shopify <mailer@shopify.com>", "New sign-in to your Shopify account", "")
    assert not is_relevant_email("Shopify <email@email.shopify.com>", "The secret behind Shopify's best stores", "")
    assert not is_relevant_email("Google <no-reply@accounts.google.com>", "Your Google Account was recovered", "")
    assert not is_relevant_email("Shopify <no-reply@shopify.com>", "Shopify verification code", "123456")


def test_real_correspondence_is_imported():
    assert is_relevant_email("Ann <ann@glasscofill.com>", "Invoice 8842 for the jar order", "attached")
    assert is_relevant_email("Lee <lee@packworks.cn>", "Quote — 5,000 pump bottles", "MOQ 5000")
    assert is_relevant_email("someone@example.com", "Re: label artwork proof", "see attached")


def test_a_business_email_from_an_automated_sender_still_counts():
    """An order confirmation or supplier invoice matters even from a robot."""
    assert is_relevant_email(
        "Shopify <no-reply@shopify.com>", "Order #1042 confirmation", "Your order # has shipped"
    )
    assert is_relevant_email(
        "billing <no-reply@vendor.com>", "Invoice for March packaging run", "amount due"
    )


# --- The endpoint ---------------------------------------------------------


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_summary_reports_an_empty_workspace_honestly(client):
    headers = _login(client, "import-empty@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    body = client.get(f"{API}/workspace-import/summary?company_id={company}", headers=headers).json()
    assert body == {"total": 0, "by_source": {}, "by_section": {}}


def test_summary_is_scoped_to_its_own_workspace(client):
    headers = _login(client, "import-scope@example.com")
    a = client.post(f"{API}/companies", json={"name": "Alpha"}, headers=headers).json()["id"]
    stranger = _login(client, "import-stranger@example.com")
    assert client.get(f"{API}/workspace-import/summary?company_id={a}", headers=stranger).json()["total"] == 0
