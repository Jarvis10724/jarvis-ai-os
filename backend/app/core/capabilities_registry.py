"""
The single place a new external-service "Capability" (Gmail, Calendar,
Shopify, QuickBooks, Amazon, ...) plugs into Jarvis. Adding one should never
require new approval, audit, permission, health-check, or scheduling code —
that machinery lives once in app.core.capability_service and is driven
entirely by the declarations here.

A Capability wraps an existing app.integrations.base.BaseIntegration (the
OAuth + API contract) with a fixed list of named actions. Each action is
tagged `requires_approval`: side-effecting calls to the outside world
(send an email, create a calendar event, refund an order) require a human
to approve an ApprovalRequest before `capability_service` will let them
execute; read-only calls (list messages, pull inventory levels) don't.

Some integration_name values below don't have a real app.integrations class
yet (contacts_crm, slack, discord) — that's fine, the registry entry can
exist ahead of the implementation. Nothing here calls the integration until
a health check or an actual action runs, so registering early costs nothing
and keeps the eventual build order (see docs/JARVIS_PHASE_3_PLAN.md) a
matter of implementing one class, not touching this framework.
"""
from dataclasses import dataclass, field

# The storefront action set, declared as data one layer down. Imported here so
# the capability's action list and the executor's dispatch table are the same
# list — see the ActionDefinition generation in the shopify entry below.
from app.core.shopify_action_registry import ACTIONS as _SHOPIFY_ACTIONS


@dataclass(frozen=True)
class ActionDefinition:
    name: str
    description: str = ""
    # True = must go through capability_service.propose_action() and wait
    # for human approval. False = read-only; capability_service.
    # authorize_direct_action() just checks the capability is enabled and
    # permitted, then the caller executes immediately.
    requires_approval: bool = False


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    description: str
    #: key into app.integrations.registry.INTEGRATION_CLASSES
    integration_name: str
    actions: list[ActionDefinition] = field(default_factory=list)

    def action(self, action_name: str) -> ActionDefinition:
        for a in self.actions:
            if a.name == action_name:
                return a
        raise KeyError(action_name)

    @property
    def default_permissions(self) -> list[str]:
        """Actions granted by default when a company enables this capability
        for the first time and hasn't set explicit permissions: every
        read-only action, none of the approval-gated ones. Write access is
        always an explicit opt-in, on top of the per-call approval gate."""
        return [a.name for a in self.actions if not a.requires_approval]


CAPABILITIES: dict[str, CapabilityDefinition] = {
    "business_data": CapabilityDefinition(
        name="business_data",
        description="Internal business data — product fields and company profile sections Jarvis's chat agent proposes changes to.",
        integration_name="business_data",
        actions=[
            ActionDefinition("update_product", "Change one or more fields on a product/SKU", requires_approval=True),
            ActionDefinition(
                "update_company_section", "Change a company profile section's status/notes", requires_approval=True
            ),
        ],
    ),
    "email": CapabilityDefinition(
        name="email",
        description="Gmail — read, search, summarize, draft, and send.",
        integration_name="email",
        actions=[
            ActionDefinition("list_messages", "List/search inbox messages (also powers 'unread only')"),
            ActionDefinition("get_message", "Fetch one full message"),
            ActionDefinition("summarize", "Summarize a message or a batch of unread messages"),
            ActionDefinition("draft", "Compose a draft or draft a reply (not sent)"),
            ActionDefinition("send", "Send an email or reply", requires_approval=True),
            ActionDefinition("forward", "Forward a message", requires_approval=True),
            ActionDefinition("trash", "Move a message to trash", requires_approval=True),
            ActionDefinition("archive", "Archive a message (remove from inbox)", requires_approval=True),
            ActionDefinition("modify_labels", "Add/remove labels on a message", requires_approval=True),
        ],
    ),
    "google_calendar": CapabilityDefinition(
        name="google_calendar",
        description="Google Calendar — view, create, update, and delete events.",
        integration_name="google_calendar",
        actions=[
            ActionDefinition("list_events", "List upcoming events"),
            ActionDefinition("get_event", "Fetch one event's details"),
            ActionDefinition("create_event", "Create a calendar event", requires_approval=True),
            ActionDefinition("update_event", "Update an existing event", requires_approval=True),
            ActionDefinition("delete_event", "Delete/cancel an event", requires_approval=True),
        ],
    ),
    "google_drive": CapabilityDefinition(
        name="google_drive",
        description="Google Drive / Docs — search and read documents.",
        integration_name="google_drive",
        actions=[
            ActionDefinition("list_files", "List/search Drive files"),
            ActionDefinition("read_document", "Read a Doc's content"),
        ],
    ),
    "contacts_crm": CapabilityDefinition(
        name="contacts_crm",
        description="Contacts & CRM — sync external contacts into Jarvis's CRM.",
        integration_name="contacts",
        actions=[
            ActionDefinition("sync_contacts", "Pull contacts from the external source"),
            ActionDefinition("create_contact_external", "Push a new contact out", requires_approval=True),
        ],
    ),
    "shopify": CapabilityDefinition(
        name="shopify",
        description="Shopify — read store catalog, orders, customers, and settings.",
        integration_name="shopify",
        actions=[
            # Phase 1: read-only. Every action here is requires_approval=False,
            # so enabling the capability auto-grants them (see
            # default_permissions) and they run through
            # authorize_direct_action() — no external writes are possible.
            ActionDefinition("list_products", "List products & variants"),
            ActionDefinition("list_collections", "List collections"),
            ActionDefinition("list_inventory", "Read inventory levels"),
            ActionDefinition("list_orders", "List recent orders"),
            ActionDefinition("list_customers", "List customers"),
            ActionDefinition("list_discounts", "List discounts / price rules"),
            ActionDefinition("list_themes", "List themes"),
            ActionDefinition("get_settings", "Read store settings"),
            ActionDefinition("list_metafields", "Read metafields"),
            ActionDefinition("list_metaobjects", "Read metaobjects"),
            # Write actions remain declared but UNIMPLEMENTED in Phase 1 —
            # approval-gated so they can never run without an explicit
            # ApprovalRequest, and no executor is registered for them.
            ActionDefinition("refund_order", "Refund an order", requires_approval=True),
            ActionDefinition("fulfill_order", "Mark an order fulfilled", requires_approval=True),
            # Storefront writes. Jarvis PREPARES these — each one becomes an
            # ApprovalRequest carrying exactly what would change. None of them
            # has a registered executor, so approving records consent and
            # nothing reaches the live store until an executor is deliberately
            # enabled. Nothing here can publish on its own.
            ActionDefinition("update_images", "Add/replace/reorder product images", requires_approval=True),
            # The full storefront action set is declared in
            # app.core.shopify_action_registry, which is also what the executor
            # dispatches on. Generating the ActionDefinitions from it means an
            # action can never exist in one place and not the other — a write
            # the capability framework doesn't know about would be a write with
            # no permission check and no approval gate.
            *(
                ActionDefinition(name, spec.label or name.replace("_", " "), requires_approval=True)
                for name, spec in _SHOPIFY_ACTIONS.items()
            ),
        ],
    ),
    "amazon": CapabilityDefinition(
        name="amazon",
        description="Amazon Seller Central — orders and listings.",
        integration_name="amazon",
        actions=[
            ActionDefinition("list_orders", "List recent orders"),
            ActionDefinition("list_listings", "List active listings"),
            ActionDefinition("update_listing", "Update a listing", requires_approval=True),
        ],
    ),
    "quickbooks": CapabilityDefinition(
        name="quickbooks",
        description="QuickBooks — real financials.",
        integration_name="quickbooks",
        actions=[
            ActionDefinition("list_transactions", "List transactions"),
            ActionDefinition("get_reports", "Pull financial reports"),
            ActionDefinition("create_invoice", "Create an invoice", requires_approval=True),
        ],
    ),
    "slack": CapabilityDefinition(
        name="slack",
        description="Slack — post messages (optional).",
        integration_name="slack",
        actions=[
            ActionDefinition("list_channels", "List channels"),
            ActionDefinition("post_message", "Post a message", requires_approval=True),
        ],
    ),
    "discord": CapabilityDefinition(
        name="discord",
        description="Discord — post messages (optional).",
        integration_name="discord",
        actions=[
            ActionDefinition("list_channels", "List channels"),
            ActionDefinition("post_message", "Post a message", requires_approval=True),
        ],
    ),
}


def get_capability(name: str) -> CapabilityDefinition:
    from app.exceptions import ValidationError

    if name not in CAPABILITIES:
        raise ValidationError(f"Unknown capability '{name}'. Available: {list(CAPABILITIES)}")
    return CAPABILITIES[name]


def list_capabilities() -> list[dict]:
    return [
        {
            "name": c.name,
            "description": c.description,
            "integration_name": c.integration_name,
            "actions": [
                {"name": a.name, "description": a.description, "requires_approval": a.requires_approval}
                for a in c.actions
            ],
        }
        for c in CAPABILITIES.values()
    ]
