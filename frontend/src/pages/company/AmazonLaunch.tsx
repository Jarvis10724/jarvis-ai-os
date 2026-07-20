import { PackageSearch } from "lucide-react";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import DataTable, { type DataTableColumn } from "@/components/DataTable";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill, { type StatusTone } from "@/components/StatusPill";
import { AMAZON_STATUS_LABELS, MOCK_LISTINGS } from "@/mock/amazonLaunch";
import type { AmazonListing } from "@/types";

const STATUS_TONE: Record<AmazonListing["status"], StatusTone> = {
  planning: "neutral",
  listing_created: "info",
  pending_review: "progress",
  live: "success",
  suppressed: "danger",
};

const COLUMNS: DataTableColumn<AmazonListing>[] = [
  { key: "title", label: "Listing", render: (l) => <span className="font-medium text-jarvis-text">{l.title}</span> },
  { key: "asin", label: "ASIN", render: (l) => l.asin ?? "Not yet assigned" },
  { key: "category", label: "Category", render: (l) => l.category ?? "—" },
  { key: "status", label: "Status", render: (l) => <StatusPill label={AMAZON_STATUS_LABELS[l.status]} tone={STATUS_TONE[l.status]} /> },
  { key: "launchDate", label: "Launch Date", render: (l) => l.launchDate ?? "TBD" },
];

export default function AmazonLaunchCenterPage() {
  return (
    <CompanyScopedPage>
      {(company) => (
        <>
          <ModulePageHeader
            icon={PackageSearch}
            title="Amazon Launch Center"
            description={`Tracking ${company.name}'s path to launching on Amazon.`}
          />

          <div className="hud-panel hud-corner shrink-0 p-4 text-xs text-jarvis-muted">
            Connects to the Amazon SP-API integration once it's set up (see Settings → Integrations) —
            that will pull real order/inventory data in. For now, this tracks launch prep manually.
          </div>

          <div className="hud-panel hud-corner min-h-0 flex-1 overflow-hidden">
            <DataTable columns={COLUMNS} rows={MOCK_LISTINGS} emptyLabel="No listings planned yet." />
          </div>
        </>
      )}
    </CompanyScopedPage>
  );
}
