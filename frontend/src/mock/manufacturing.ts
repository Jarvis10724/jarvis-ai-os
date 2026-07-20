// MOCK DATA — replace with a real `production_runs` table once connected.
// Complements the existing `Product` model (launch_status) with the
// day-to-day tracking a single "status" field can't capture.
import type { ProductionRun } from "@/types";

export const MOCK_PRODUCTION_RUNS: ProductionRun[] = [
  {
    id: "r1",
    productName: "Primal Penni — Flagship Blend, 12oz",
    stage: "in_production",
    quantity: 2000,
    factory: "Coastal Co-Pack Partners",
    eta: "2026-08-05",
    notes: "Second production run — first sold out in 6 weeks.",
  },
  {
    id: "r2",
    productName: "Primal Penni — Travel Size 3-Pack",
    stage: "sampling",
    quantity: 500,
    factory: "Coastal Co-Pack Partners",
    eta: null,
    notes: "Waiting on final packaging samples before approving.",
  },
  {
    id: "r3",
    productName: "Primal Penni — Gift Box Set",
    stage: "sourcing",
    quantity: 0,
    factory: null,
    eta: null,
    notes: "Getting quotes from 2 additional co-packers for comparison.",
  },
  {
    id: "r4",
    productName: "Primal Penni — Flagship Blend, 12oz (Run #1)",
    stage: "complete",
    quantity: 1500,
    factory: "Coastal Co-Pack Partners",
    eta: "2026-05-20",
    notes: "Fully sold through.",
  },
];

export const MANUFACTURING_STAGE_LABELS: Record<ProductionRun["stage"], string> = {
  sourcing: "Sourcing",
  sampling: "Sampling",
  in_production: "In Production",
  quality_check: "Quality Check",
  shipping: "Shipping",
  complete: "Complete",
};
