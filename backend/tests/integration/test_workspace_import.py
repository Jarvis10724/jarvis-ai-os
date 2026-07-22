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


# --- Deep extraction ------------------------------------------------------


def test_brand_extraction_stores_structured_data_not_links(client, monkeypatch):
    """The point of the deep pass: fields on the section, not another list of
    document references."""
    import asyncio
    import json as _json

    from app.core import workspace_import_service as wi
    from app.db.models.company import Company
    from app.db.session import SessionLocal

    headers = _login(client, "brand-extract@example.com")
    company_id = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]

    async def fake_files(*_a, **_k):
        return [
            {"id": "f1", "name": "Primary Logo_Sacred Ash.png", "mime_type": "image/png",
             "web_view_link": "https://drive.google.com/file/d/f1"},
            {"id": "f2", "name": "Sofia Pro Bold.otf", "mime_type": "font/otf",
             "web_view_link": "https://drive.google.com/file/d/f2"},
            {"id": "f3", "name": "Brand Guidelines", "mime_type": "application/vnd.google-apps.document",
             "web_view_link": "https://drive.google.com/file/d/f3"},
        ]

    async def fake_read(_db, **kwargs):
        return {"id": kwargs["file_id"], "name": "Brand Guidelines",
                "content": "Our palette is #1A2B3C and #FFEEDD. Follow us at https://instagram.com/primalpenni",
                "extractable": True}

    class _Result:
        text = _json.dumps({"tagline": "Ritual, not routine", "mission": "Clean skincare as daily ceremony",
                            "brand_story": None, "voice": "Earthy", "values": ["ritual"]})
        tool_calls: list = []
        content_blocks = None

    class _Provider:
        async def complete(self, *_a, **_k):
            return _Result()

    monkeypatch.setattr(wi.drive_service, "list_files", fake_files)
    monkeypatch.setattr(wi.drive_service, "read_document", fake_read)
    monkeypatch.setattr("app.ai_providers.factory.get_ai_provider", lambda: _Provider())

    db = SessionLocal()
    try:
        owner_id = db.query(Company).filter(Company.id == company_id).first().owner_id
        brief = asyncio.get_event_loop().run_until_complete(
            wi.extract_brand(db, owner_id=owner_id, company_id=company_id)
        )
    finally:
        db.close()

    assert brief["company_name"] == "SPN Group LLC"
    assert brief["logo"]["name"] == "Primary Logo_Sacred Ash.png"      # located, not just listed
    assert "Sofia Pro Bold.otf" in brief["fonts"]
    assert "#1A2B3C" in brief["colors"] and "#FFEEDD" in brief["colors"]
    assert any("instagram.com" in s for s in brief["social_links"])
    assert brief["tagline"] == "Ritual, not routine"
    assert brief["brand_story"] is None                                 # unstated stays null

    # And it lands on the section as structured data the UI can render.
    stored = client.get(f"{API}/companies/{company_id}", headers=headers).json()
    assert stored["sections"]["brand"]["data"]["logo"]["name"] == "Primary Logo_Sacred Ash.png"


def test_extraction_never_overwrites_what_a_human_wrote(client, monkeypatch):
    from app.core import workspace_import_service as wi
    from app.db.models.company import Company
    from app.db.session import SessionLocal

    headers = _login(client, "brand-manual@example.com")
    company_id = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        wi._store_section_data(db, company, "brand", {"tagline": "Written by hand"})
        # A later extraction that finds no tagline must not blank it.
        wi._store_section_data(db, company, "brand", {"tagline": None, "mission": "Found in a doc"})
        db.refresh(company)
        import json as _json
        data = _json.loads(company.sections_json)["brand"]["data"]
    finally:
        db.close()

    assert data["tagline"] == "Written by hand"
    assert data["mission"] == "Found in a doc"


def test_unsupported_section_says_so_rather_than_pretending(client):
    headers = _login(client, "extract-unsupported@example.com")
    company_id = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    body = client.post(
        f"{API}/workspace-import/extract?company_id={company_id}&section=manufacturing", headers=headers
    ).json()
    assert body["supported"] is False and "isn't implemented yet" in body["message"]
