import { Factory } from "lucide-react";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import DataTable, { type DataTableColumn } from "@/components/DataTable";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill, { type StatusTone } from "@/components/StatusPill";
import { MANUFACTURING_STAGE_LABELS, MOCK_PRODUCTION_RUNS } from "@/mock/manufacturing";
import type { ProductionRun } from "@/types";

const STAGE_TONE: Record<ProductionRun["stage"], StatusTone> = {
  sourcing: "neutral",
  sampling: "info",
  in_production: "progress",
  quality_check: "progress",
  shipping: "accent",
  complete: "success",
};

const COLUMNS: DataTableColumn<ProductionRun>[] = [
  { key: "productName", label: "Product", render: (r) => <span className="font-medium text-jarvis-text">{r.productName}</span> },
  {
    key: "stage",
    label: "Stage",
    render: (r) => <StatusPill label={MANUFACTURING_STAGE_LABELS[r.stage]} tone={STAGE_TONE[r.stage]} />,
  },
  { key: "quantity", label: "Qty", render: (r) => r.quantity.toLocaleString() },
  { key: "factory", label: "Factory / Co-Packer", render: (r) => r.factory ?? "—" },
  { key: "eta", label: "ETA", render: (r) => r.eta ?? "—" },
  { key: "notes", label: "Notes", render: (r) => <span className="text-xs text-jarvis-muted">{r.notes || "—"}</span> },
];

export default function ManufacturingTrackerPage() {
  return (
    <CompanyScopedPage>
      {(company) => (
        <>
          <ModulePageHeader
            icon={Factory}
            title="Manufacturing Tracker"
            description={`Production runs in flight for ${company.name}, from sourcing to shipped.`}
          />
          <div className="hud-panel hud-corner min-h-0 flex-1 overflow-hidden">
            <DataTable columns={COLUMNS} rows={MOCK_PRODUCTION_RUNS} emptyLabel="No production runs tracked yet." />
          </div>
        </>
      )}
    </CompanyScopedPage>
  );
}
