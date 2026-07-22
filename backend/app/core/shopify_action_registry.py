"""
Every storefront action Jarvis can propose, declared as data.

The commit SEQUENCE — read live, refuse if stale, mutate, refuse on
userErrors, read back, refuse unless it matches — is written once in
shopify_write_service. This module is what that sequence is applied TO, so
adding an action means adding a row here rather than another code path that
might forget a safety step.

Each ActionSpec answers four questions:

  * which OAuth scope does it need?           -> scope
  * which fields does it change?              -> fields (payload key -> live key)
  * how is it sent?                           -> mutation / variables()
  * can the result be verified by re-reading? -> verifies

`verifies=False` is deliberate and load-bearing. A create, a duplicate, or a
delete has no "before" to diff and no prior value to compare a read-back
against, so claiming "verified" for one would be a lie. Those report what
Shopify returned (the new id) and say plainly that the check performed was
existence, not equality.

TARGET tells the executor what a change is aimed at — a product, a collection,
a discount, a page — because "read the current value" means a different query
for each.
"""
from dataclasses import dataclass, field
from typing import Callable

# --- GraphQL ---------------------------------------------------------------

PRODUCT_UPDATE = """
mutation ProductUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id title handle status descriptionHtml vendor productType tags }
    userErrors { field message }
  }
}
"""

PRODUCT_CREATE = """
mutation ProductCreate($input: ProductInput!) {
  productCreate(input: $input) { product { id title handle status } userErrors { field message } }
}
"""

PRODUCT_DUPLICATE = """
mutation ProductDuplicate($productId: ID!, $newTitle: String!, $includeImages: Boolean) {
  productDuplicate(productId: $productId, newTitle: $newTitle, includeImages: $includeImages) {
    newProduct { id title handle status } userErrors { field message }
  }
}
"""

VARIANTS_BULK_UPDATE = """
mutation VariantsUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id price compareAtPrice sku barcode }
    userErrors { field message }
  }
}
"""

INVENTORY_SET = """
mutation InventorySet($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup { createdAt reason } userErrors { field message }
  }
}
"""

INVENTORY_ITEM_UPDATE = """
mutation InventoryItemUpdate($id: ID!, $input: InventoryItemInput!) {
  inventoryItemUpdate(id: $id, input: $input) {
    inventoryItem { id tracked measurement { weight { value unit } } }
    userErrors { field message }
  }
}
"""

MEDIA_CREATE = """
mutation MediaCreate($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media { ... on MediaImage { id } } mediaUserErrors { field message }
  }
}
"""

MEDIA_DELETE = """
mutation MediaDelete($productId: ID!, $mediaIds: [ID!]!) {
  productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
    deletedMediaIds mediaUserErrors { field message }
  }
}
"""

MEDIA_REORDER = """
mutation MediaReorder($id: ID!, $moves: [MoveInput!]!) {
  productReorderMedia(id: $id, moves: $moves) { job { id } mediaUserErrors { field message } }
}
"""

COLLECTION_CREATE = """
mutation CollectionCreate($input: CollectionInput!) {
  collectionCreate(input: $input) { collection { id title handle } userErrors { field message } }
}
"""

COLLECTION_UPDATE = """
mutation CollectionUpdate($input: CollectionInput!) {
  collectionUpdate(input: $input) { collection { id title handle } userErrors { field message } }
}
"""

COLLECTION_DELETE = """
mutation CollectionDelete($input: CollectionDeleteInput!) {
  collectionDelete(input: $input) { deletedCollectionId userErrors { field message } }
}
"""

COLLECTION_ADD_PRODUCTS = """
mutation CollectionAddProducts($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    collection { id } userErrors { field message }
  }
}
"""

COLLECTION_REMOVE_PRODUCTS = """
mutation CollectionRemoveProducts($id: ID!, $productIds: [ID!]!) {
  collectionRemoveProducts(id: $id, productIds: $productIds) { job { id } userErrors { field message } }
}
"""

DISCOUNT_CREATE = """
mutation DiscountCreate($basicCodeDiscount: DiscountCodeBasicInput!) {
  discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
    codeDiscountNode { id } userErrors { field message }
  }
}
"""

DISCOUNT_UPDATE = """
mutation DiscountUpdate($id: ID!, $basicCodeDiscount: DiscountCodeBasicInput!) {
  discountCodeBasicUpdate(id: $id, basicCodeDiscount: $basicCodeDiscount) {
    codeDiscountNode { id } userErrors { field message }
  }
}
"""

DISCOUNT_ACTIVATE = """
mutation DiscountActivate($id: ID!) {
  discountCodeActivate(id: $id) { codeDiscountNode { id } userErrors { field message } }
}
"""

DISCOUNT_DEACTIVATE = """
mutation DiscountDeactivate($id: ID!) {
  discountCodeDeactivate(id: $id) { codeDiscountNode { id } userErrors { field message } }
}
"""

DISCOUNT_DELETE = """
mutation DiscountDelete($id: ID!) {
  discountCodeDelete(id: $id) { deletedCodeDiscountId userErrors { field message } }
}
"""

PAGE_CREATE = """
mutation PageCreate($page: PageCreateInput!) {
  pageCreate(page: $page) { page { id title handle isPublished } userErrors { field message } }
}
"""

PAGE_UPDATE = """
mutation PageUpdate($id: ID!, $page: PageUpdateInput!) {
  pageUpdate(id: $id, page: $page) { page { id title handle isPublished } userErrors { field message } }
}
"""

PAGE_DELETE = """
mutation PageDelete($id: ID!) { pageDelete(id: $id) { deletedPageId userErrors { field message } } }
"""

MENU_UPDATE = """
mutation MenuUpdate($id: ID!, $title: String!, $items: [MenuItemUpdateInput!]!) {
  menuUpdate(id: $id, title: $title, items: $items) { menu { id title } userErrors { field message } }
}
"""


# --- The spec --------------------------------------------------------------


@dataclass(frozen=True)
class ActionSpec:
    """One storefront action."""

    #: OAuth scope Shopify requires. Checked against what the app actually holds.
    scope: str
    #: What the action is aimed at: product | collection | discount | page | menu.
    target: str
    #: payload key -> key on the live-read record holding the CURRENT value.
    #: Drives both the before/after preview and the post-write verification.
    fields: dict[str, str] = field(default_factory=dict)
    #: The GraphQL document. None means declared-but-not-implemented; the
    #: executor refuses those by name instead of pretending.
    mutation: str | None = None
    #: (live_record, payload) -> GraphQL variables.
    variables: Callable[[dict, dict], dict] | None = None
    #: The mutation's root field, for reading userErrors off the response.
    root: str = ""
    #: Can the outcome be proven by re-reading and comparing? False for
    #: create/duplicate/delete, where there is no prior value to compare to.
    verifies: bool = True
    #: Human label, used in briefs and the UI.
    label: str = ""


def _product_input(live: dict, payload: dict, keys: dict[str, str]) -> dict:
    """{id, …} for productUpdate, carrying only the keys actually supplied."""
    out: dict = {"id": live["id"]}
    for payload_key, graphql_key in keys.items():
        if payload.get(payload_key) is not None:
            out[graphql_key] = payload[payload_key]
    return out


def _status(value: str) -> str:
    return str(value).strip().upper()


ACTIONS: dict[str, ActionSpec] = {
    # --- Products ---------------------------------------------------------
    "update_product": ActionSpec(
        scope="write_products", target="product", label="Edit title / description / status",
        fields={"title": "title", "description": "description", "status": "status"},
        mutation=PRODUCT_UPDATE, root="productUpdate",
        variables=lambda live, p: {"input": {
            **_product_input(live, p, {"title": "title", "description": "descriptionHtml"}),
            **({"status": _status(p["status"])} if p.get("status") is not None else {}),
        }},
    ),
    "update_product_details": ActionSpec(
        scope="write_products", target="product", label="Edit vendor / type / tags",
        fields={"vendor": "vendor", "product_type": "product_type", "tags": "tags"},
        mutation=PRODUCT_UPDATE, root="productUpdate",
        variables=lambda live, p: {"input": _product_input(
            live, p, {"vendor": "vendor", "product_type": "productType", "tags": "tags"}
        )},
    ),
    "update_seo": ActionSpec(
        scope="write_products", target="product", label="Edit SEO title / description",
        fields={"seo_title": "seo_title", "seo_description": "seo_description"},
        mutation=PRODUCT_UPDATE, root="productUpdate",
        variables=lambda live, p: {"input": {"id": live["id"], "seo": {
            **({"title": p["seo_title"]} if p.get("seo_title") is not None else {}),
            **({"description": p["seo_description"]} if p.get("seo_description") is not None else {}),
        }}},
    ),
    "publish_product": ActionSpec(
        scope="write_products", target="product", label="Make the product live",
        fields={"status": "status"}, mutation=PRODUCT_UPDATE, root="productUpdate",
        variables=lambda live, p: {"input": {"id": live["id"], "status": _status(p.get("status") or "ACTIVE")}},
    ),
    "unpublish_product": ActionSpec(
        scope="write_products", target="product", label="Take the product off the storefront",
        fields={"status": "status"}, mutation=PRODUCT_UPDATE, root="productUpdate",
        variables=lambda live, _p: {"input": {"id": live["id"], "status": "DRAFT"}},
    ),
    "archive_product": ActionSpec(
        scope="write_products", target="product", label="Archive the product",
        fields={"status": "status"}, mutation=PRODUCT_UPDATE, root="productUpdate",
        variables=lambda live, _p: {"input": {"id": live["id"], "status": "ARCHIVED"}},
    ),
    "restore_product": ActionSpec(
        scope="write_products", target="product", label="Restore an archived product to draft",
        fields={"status": "status"}, mutation=PRODUCT_UPDATE, root="productUpdate",
        variables=lambda live, p: {"input": {"id": live["id"], "status": _status(p.get("status") or "DRAFT")}},
    ),
    "create_draft_product": ActionSpec(
        scope="write_products", target="product", label="Create a product as a draft",
        mutation=PRODUCT_CREATE, root="productCreate", verifies=False,
        variables=lambda _live, p: {"input": {
            "title": p["title"],
            # A new product is ALWAYS created as a draft, whatever was asked
            # for. Publishing is its own action, with its own approval.
            "status": "DRAFT",
            **({"descriptionHtml": p["description"]} if p.get("description") else {}),
            **({"vendor": p["vendor"]} if p.get("vendor") else {}),
            **({"productType": p["product_type"]} if p.get("product_type") else {}),
            **({"tags": p["tags"]} if p.get("tags") else {}),
        }},
    ),
    "duplicate_product": ActionSpec(
        scope="write_products", target="product", label="Duplicate a product",
        mutation=PRODUCT_DUPLICATE, root="productDuplicate", verifies=False,
        variables=lambda live, p: {
            "productId": live["id"],
            "newTitle": p.get("new_title") or f"{live.get('title')} (copy)",
            "includeImages": bool(p.get("include_images", True)),
        },
    ),
    # --- Variants ---------------------------------------------------------
    "update_price": ActionSpec(
        scope="write_products", target="product", label="Change price",
        fields={"price": "price"}, mutation=VARIANTS_BULK_UPDATE, root="productVariantsBulkUpdate",
        variables=lambda live, p: {"productId": live["id"], "variants": [
            {"id": live["variant_id"], "price": str(p["price"])}
        ]},
    ),
    "update_compare_at_price": ActionSpec(
        scope="write_products", target="product", label="Change compare-at price",
        fields={"compare_at_price": "compare_at_price"},
        mutation=VARIANTS_BULK_UPDATE, root="productVariantsBulkUpdate",
        variables=lambda live, p: {"productId": live["id"], "variants": [
            {"id": live["variant_id"], "compareAtPrice": str(p["compare_at_price"])}
        ]},
    ),
    "update_variant": ActionSpec(
        scope="write_products", target="product", label="Edit SKU / barcode / price",
        fields={"sku": "sku", "barcode": "barcode", "price": "price"},
        mutation=VARIANTS_BULK_UPDATE, root="productVariantsBulkUpdate",
        variables=lambda live, p: {"productId": live["id"], "variants": [{
            "id": p.get("variant_id") or live["variant_id"],
            **({"sku": p["sku"]} if p.get("sku") is not None else {}),
            **({"barcode": p["barcode"]} if p.get("barcode") is not None else {}),
            **({"price": str(p["price"])} if p.get("price") is not None else {}),
        }]},
    ),
    "update_weight": ActionSpec(
        scope="write_inventory", target="product", label="Change weight",
        fields={"weight": "weight"}, mutation=INVENTORY_ITEM_UPDATE, root="inventoryItemUpdate",
        variables=lambda live, p: {"id": live["inventory_item_id"], "input": {
            "measurement": {"weight": {
                "value": float(p["weight"]),
                "unit": str(p.get("weight_unit") or "GRAMS").upper(),
            }}
        }},
    ),
    # --- Images -----------------------------------------------------------
    "add_images": ActionSpec(
        scope="write_products", target="product", label="Add product images",
        mutation=MEDIA_CREATE, root="productCreateMedia", verifies=False,
        variables=lambda live, p: {"productId": live["id"], "media": [
            {"originalSource": url, "mediaContentType": "IMAGE",
             "alt": (p.get("alt_text") or "")} for url in (p.get("image_urls") or [])
        ]},
    ),
    "remove_images": ActionSpec(
        scope="write_products", target="product", label="Remove product images",
        mutation=MEDIA_DELETE, root="productDeleteMedia", verifies=False,
        variables=lambda live, p: {"productId": live["id"], "mediaIds": p.get("media_ids") or []},
    ),
    "reorder_images": ActionSpec(
        scope="write_products", target="product", label="Reorder product images",
        mutation=MEDIA_REORDER, root="productReorderMedia", verifies=False,
        variables=lambda live, p: {"id": live["id"], "moves": [
            {"id": m["id"], "newPosition": str(m["position"])} for m in (p.get("moves") or [])
        ]},
    ),
    # --- Inventory --------------------------------------------------------
    "update_inventory": ActionSpec(
        scope="write_inventory", target="product", label="Change stock level",
        fields={"quantity": "quantity"}, mutation=INVENTORY_SET, root="inventorySetQuantities",
        variables=lambda live, p: {"input": {
            "name": "available", "reason": "correction", "ignoreCompareQuantity": True,
            "quantities": [{
                "inventoryItemId": live["inventory_item_id"],
                "locationId": p.get("location_id") or live["location_id"],
                "quantity": int(p["quantity"]),
            }],
        }},
    ),
    "set_inventory_tracking": ActionSpec(
        scope="write_inventory", target="product", label="Turn stock tracking on/off",
        fields={"tracked": "tracked"}, mutation=INVENTORY_ITEM_UPDATE, root="inventoryItemUpdate",
        variables=lambda live, p: {"id": live["inventory_item_id"],
                                   "input": {"tracked": bool(p["tracked"])}},
    ),
    "set_continue_selling": ActionSpec(
        scope="write_products", target="product", label="Allow/stop selling when out of stock",
        fields={"continue_selling": "continue_selling"},
        mutation=VARIANTS_BULK_UPDATE, root="productVariantsBulkUpdate",
        variables=lambda live, p: {"productId": live["id"], "variants": [{
            "id": live["variant_id"],
            "inventoryPolicy": "CONTINUE" if p["continue_selling"] else "DENY",
        }]},
    ),
    # --- Collections ------------------------------------------------------
    "create_collection": ActionSpec(
        scope="write_products", target="collection", label="Create a collection",
        mutation=COLLECTION_CREATE, root="collectionCreate", verifies=False,
        variables=lambda _live, p: {"input": {
            "title": p["title"],
            **({"descriptionHtml": p["description"]} if p.get("description") else {}),
        }},
    ),
    "update_collection": ActionSpec(
        scope="write_products", target="collection", label="Edit a collection",
        fields={"title": "title", "description": "description"},
        mutation=COLLECTION_UPDATE, root="collectionUpdate",
        variables=lambda live, p: {"input": _product_input(
            live, p, {"title": "title", "description": "descriptionHtml"}
        )},
    ),
    "delete_collection": ActionSpec(
        scope="write_products", target="collection", label="Delete a collection",
        mutation=COLLECTION_DELETE, root="collectionDelete", verifies=False,
        variables=lambda live, _p: {"input": {"id": live["id"]}},
    ),
    "collection_add_products": ActionSpec(
        scope="write_products", target="collection", label="Add products to a collection",
        mutation=COLLECTION_ADD_PRODUCTS, root="collectionAddProducts", verifies=False,
        variables=lambda live, p: {"id": live["id"], "productIds": p.get("product_ids") or []},
    ),
    "collection_remove_products": ActionSpec(
        scope="write_products", target="collection", label="Remove products from a collection",
        mutation=COLLECTION_REMOVE_PRODUCTS, root="collectionRemoveProducts", verifies=False,
        variables=lambda live, p: {"id": live["id"], "productIds": p.get("product_ids") or []},
    ),
    # --- Discounts --------------------------------------------------------
    "create_discount": ActionSpec(
        scope="write_discounts", target="discount", label="Create a discount code",
        mutation=DISCOUNT_CREATE, root="discountCodeBasicCreate", verifies=False,
        variables=lambda _live, p: {"basicCodeDiscount": {
            "title": p.get("title") or p["code"],
            "code": p["code"],
            "startsAt": p.get("starts_at"),
            "endsAt": p.get("ends_at"),
            "customerSelection": {"all": True},
            "customerGets": {
                "items": {"all": True},
                "value": (
                    {"percentage": float(p["percentage"]) / 100}
                    if p.get("percentage") is not None
                    else {"discountAmount": {"amount": str(p["amount"]), "appliesOnEachItem": False}}
                ),
            },
        }},
    ),
    "update_discount": ActionSpec(
        scope="write_discounts", target="discount", label="Edit a discount",
        fields={"title": "title"}, mutation=DISCOUNT_UPDATE, root="discountCodeBasicUpdate",
        verifies=False,
        variables=lambda live, p: {"id": live["id"], "basicCodeDiscount": {
            **({"title": p["title"]} if p.get("title") else {}),
            **({"endsAt": p["ends_at"]} if p.get("ends_at") else {}),
        }},
    ),
    "pause_discount": ActionSpec(
        scope="write_discounts", target="discount", label="Pause a discount",
        fields={"status": "status"}, mutation=DISCOUNT_DEACTIVATE, root="discountCodeDeactivate",
        variables=lambda live, _p: {"id": live["id"]},
    ),
    "resume_discount": ActionSpec(
        scope="write_discounts", target="discount", label="Resume a discount",
        fields={"status": "status"}, mutation=DISCOUNT_ACTIVATE, root="discountCodeActivate",
        variables=lambda live, _p: {"id": live["id"]},
    ),
    "delete_discount": ActionSpec(
        scope="write_discounts", target="discount", label="Delete a discount",
        mutation=DISCOUNT_DELETE, root="discountCodeDelete", verifies=False,
        variables=lambda live, _p: {"id": live["id"]},
    ),
    # --- Store content ----------------------------------------------------
    "create_page": ActionSpec(
        scope="write_content", target="page", label="Create a page",
        mutation=PAGE_CREATE, root="pageCreate", verifies=False,
        variables=lambda _live, p: {"page": {
            "title": p["title"],
            "body": p.get("body") or "",
            "isPublished": bool(p.get("published", False)),
        }},
    ),
    "update_page": ActionSpec(
        scope="write_content", target="page", label="Edit a page",
        fields={"title": "title", "body": "body"},
        mutation=PAGE_UPDATE, root="pageUpdate",
        variables=lambda live, p: {"id": live["id"], "page": {
            **({"title": p["title"]} if p.get("title") is not None else {}),
            **({"body": p["body"]} if p.get("body") is not None else {}),
        }},
    ),
    "publish_page": ActionSpec(
        scope="write_content", target="page", label="Publish / unpublish a page",
        fields={"published": "published"}, mutation=PAGE_UPDATE, root="pageUpdate",
        variables=lambda live, p: {"id": live["id"],
                                   "page": {"isPublished": bool(p.get("published", True))}},
    ),
    "delete_page": ActionSpec(
        scope="write_content", target="page", label="Delete a page",
        mutation=PAGE_DELETE, root="pageDelete", verifies=False,
        variables=lambda live, _p: {"id": live["id"]},
    ),
    "update_menu": ActionSpec(
        scope="write_content", target="menu", label="Edit a navigation menu",
        fields={"title": "title"}, mutation=MENU_UPDATE, root="menuUpdate", verifies=False,
        variables=lambda live, p: {
            "id": live["id"],
            "title": p.get("title") or live.get("title"),
            "items": p.get("items") or [],
        },
    ),
    # --- Declared, deliberately NOT implemented ---------------------------
    # These are theme-editor concerns, not Admin API resources: the
    # announcement bar, homepage banners/images, and featured product or
    # collection blocks live in the theme's settings_data.json and section
    # templates. Writing them means editing theme assets — a different scope
    # (write_themes), a different failure mode (a malformed edit takes the
    # storefront down), and no per-field read-back to verify against. They are
    # declared so a proposal for one is REFUSED by name rather than silently
    # doing nothing or, worse, guessing at a theme's schema.
    "update_announcement_bar": ActionSpec(
        scope="write_themes", target="theme", label="Edit the announcement bar", verifies=False),
    "update_homepage_banner": ActionSpec(
        scope="write_themes", target="theme", label="Change a homepage banner", verifies=False),
    "update_homepage_images": ActionSpec(
        scope="write_themes", target="theme", label="Change homepage images", verifies=False),
    "update_featured_products": ActionSpec(
        scope="write_themes", target="theme", label="Change featured products/collections",
        verifies=False),
}

#: Scopes the app must hold for the implemented actions.
REQUIRED_SCOPES: dict[str, str] = {name: spec.scope for name, spec in ACTIONS.items()}

#: Actions that reach a real Admin API call today.
IMPLEMENTED = {name for name, spec in ACTIONS.items() if spec.mutation is not None}


def get(action_type: str) -> ActionSpec | None:
    return ACTIONS.get(action_type)
