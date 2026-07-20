// MOCK DATA — replace with a real `sop_documents` table once this module
// is backed by persistence. In the meantime this is a genuinely useful
// starting library you can edit directly in code or copy into real docs.
import type { SopDocument } from "@/types";

export const MOCK_SOPS: SopDocument[] = [
  {
    id: "s1",
    title: "Order Fulfillment (Shopify → Shipped)",
    category: "Operations",
    owner: "Nick",
    lastUpdated: "2026-07-10",
    summary: "Steps from a new Shopify order landing to it being shipped and marked fulfilled.",
    steps: [
      "Check new orders in Shopify admin each morning and evening",
      "Verify inventory is available; flag backorders immediately",
      "Print packing slip and pick items",
      "Pack per product-specific packaging SOP",
      "Generate shipping label and mark order fulfilled in Shopify",
      "Send tracking confirmation if not automated",
    ],
  },
  {
    id: "s2",
    title: "New Consulting Client Onboarding",
    category: "Consulting",
    owner: "Nick",
    lastUpdated: "2026-06-30",
    summary: "What happens between a signed proposal and the first working session.",
    steps: [
      "Send contract and invoice for first payment",
      "Set up shared folder and project tracker",
      "Schedule kickoff call within 5 business days",
      "Send pre-kickoff questionnaire",
      "Add client to CRM as 'won' and log key contacts",
    ],
  },
  {
    id: "s3",
    title: "Monthly Bookkeeping Close",
    category: "Finance",
    owner: "Nick",
    lastUpdated: "2026-07-01",
    summary: "Closing the books each month across all companies before reviewing financials.",
    steps: [
      "Reconcile all bank and credit card accounts",
      "Categorize any uncategorized transactions",
      "Review and log receipts for anything over $75",
      "Update the Financial Dashboard summary",
      "Set aside estimated tax percentage into savings",
    ],
  },
  {
    id: "s4",
    title: "New Product Manufacturing Kickoff",
    category: "Manufacturing",
    owner: null,
    lastUpdated: "2026-06-15",
    summary: "Steps to take a new product from sourcing to first production run.",
    steps: [
      "Get 3 manufacturer quotes with MOQ and lead time",
      "Order and review samples",
      "Finalize spec sheet and packaging requirements",
      "Place first production order",
      "Track production in the Manufacturing Tracker through shipping",
    ],
  },
];

export const SOP_CATEGORIES = Array.from(new Set(MOCK_SOPS.map((s) => s.category)));
