// MOCK DATA — note this one's different from the other mock files: the
// Shopify integration's read-only calls (list_products, list_orders)
// already work against the real Admin API once SHOPIFY_SHOP_URL /
// SHOPIFY_ACCESS_TOKEN are set (see
// backend/app/integrations/shopify_integration.py). This snapshot stays
// mock on the dashboard until Phase 6 wires those live results in here —
// the backend groundwork just hasn't been surfaced in the UI yet.
export interface ShopifySnapshot {
  ordersToday: number;
  revenueToday: number;
  abandonedCarts: number;
  topProduct: string;
}

export const MOCK_SHOPIFY_SNAPSHOT: ShopifySnapshot = {
  ordersToday: 14,
  revenueToday: 862,
  abandonedCarts: 5,
  topProduct: "Flagship Blend, 12oz",
};
