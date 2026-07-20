// MOCK DATA — replace with a real `inventory_items` table (or a live sync
// from Shopify/Amazon once those integrations are connected) later.
import type { InventoryItem } from "@/types";

export const MOCK_INVENTORY: InventoryItem[] = [
  {
    id: "i1",
    sku: "PP-FLAG-12OZ",
    name: "Flagship Blend, 12oz",
    warehouse: "Home / Garage",
    onHand: 340,
    reserved: 28,
    reorderPoint: 150,
    unitCost: 6.2,
  },
  {
    id: "i2",
    sku: "PP-TRAV-3PK",
    name: "Travel Size 3-Pack",
    warehouse: "Home / Garage",
    onHand: 0,
    reserved: 0,
    reorderPoint: 50,
    unitCost: 4.1,
  },
  {
    id: "i3",
    sku: "PP-GIFT-BOX",
    name: "Gift Box Set",
    warehouse: null,
    onHand: 0,
    reserved: 0,
    reorderPoint: 25,
    unitCost: null,
  },
  {
    id: "i4",
    sku: "PP-PACK-MAILER",
    name: "Branded shipping mailers",
    warehouse: "Home / Garage",
    onHand: 620,
    reserved: 0,
    reorderPoint: 200,
    unitCost: 0.35,
  },
];
