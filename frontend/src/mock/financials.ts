// MOCK DATA — replace with QuickBooks-sourced figures once that
// integration is connected (see app/integrations/quickbooks_integration.py
// on the backend — it's stubbed, same "connect later" pattern as Shopify).
import type { FinancialSummary, MetricPoint, TransactionItem } from "@/types";

export const MOCK_FINANCIAL_SUMMARY: FinancialSummary = {
  revenue: 18420,
  expenses: 11250,
  profit: 7170,
  cashOnHand: 42300,
  asOf: "2026-07-15",
};

export const MOCK_MONTHLY_TREND: MetricPoint[] = [
  { label: "Feb", value: 9200 },
  { label: "Mar", value: 11400 },
  { label: "Apr", value: 10100 },
  { label: "May", value: 14800 },
  { label: "Jun", value: 16200 },
  { label: "Jul", value: 18420 },
];

export const MOCK_TRANSACTIONS: TransactionItem[] = [
  { id: "t1", date: "2026-07-14", description: "Shopify payout", category: "Sales", amount: 3120, type: "income" },
  { id: "t2", date: "2026-07-13", description: "Coastal Co-Pack Partners — production deposit", category: "COGS", amount: 4200, type: "expense" },
  { id: "t3", date: "2026-07-12", description: "Consulting retainer — Whitfield & Co.", category: "Consulting Revenue", amount: 2800, type: "income" },
  { id: "t4", date: "2026-07-10", description: "Meta ads", category: "Marketing", amount: 640, type: "expense" },
  { id: "t5", date: "2026-07-08", description: "Shipping supplies", category: "Operations", amount: 210, type: "expense" },
  { id: "t6", date: "2026-07-05", description: "Wholesale order — Coastal Market Co-op", category: "Sales", amount: 3100, type: "income" },
];
