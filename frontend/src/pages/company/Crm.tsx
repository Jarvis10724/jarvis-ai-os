import { Users } from "lucide-react";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import DataTable, { type DataTableColumn } from "@/components/DataTable";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill, { type StatusTone } from "@/components/StatusPill";
import { CRM_STAGE_LABELS, MOCK_CONTACTS } from "@/mock/crm";
import type { CrmContact } from "@/types";

const STAGE_TONE: Record<CrmContact["stage"], StatusTone> = {
  lead: "neutral",
  contacted: "info",
  proposal: "progress",
  won: "success",
  lost: "danger",
};

const COLUMNS: DataTableColumn<CrmContact>[] = [
  {
    key: "name",
    label: "Contact",
    render: (c) => (
      <div>
        <p className="font-medium text-jarvis-text">{c.name}</p>
        {c.company && <p className="text-xs text-jarvis-muted">{c.company}</p>}
      </div>
    ),
  },
  {
    key: "stage",
    label: "Stage",
    render: (c) => <StatusPill label={CRM_STAGE_LABELS[c.stage]} tone={STAGE_TONE[c.stage]} />,
  },
  {
    key: "value",
    label: "Value",
    render: (c) => (c.value ? `$${c.value.toLocaleString()}` : "—"),
  },
  {
    key: "lastContact",
    label: "Last Contact",
    render: (c) => c.lastContact ?? "Never",
  },
  {
    key: "contact",
    label: "Reach",
    render: (c) => (
      <div className="text-xs text-jarvis-muted">
        {c.email && <p>{c.email}</p>}
        {c.phone && <p>{c.phone}</p>}
        {!c.email && !c.phone && "—"}
      </div>
    ),
  },
];

export default function CrmPage() {
  return (
    <CompanyScopedPage>
      {(company) => {
        const totalPipeline = MOCK_CONTACTS.filter((c) => c.stage === "proposal" || c.stage === "contacted").reduce(
          (sum, c) => sum + (c.value ?? 0),
          0
        );

        return (
          <>
            <ModulePageHeader
              icon={Users}
              title="CRM"
              description={`Contacts and pipeline for ${company.name}.`}
              actions={
                <div className="rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/50 px-3 py-2 text-right">
                  <p className="text-[10px] uppercase tracking-wide text-jarvis-muted">Open Pipeline</p>
                  <p className="font-display text-sm font-bold text-jarvis-cyan">
                    ${totalPipeline.toLocaleString()}
                  </p>
                </div>
              }
            />
            <div className="hud-panel hud-corner min-h-0 flex-1 overflow-hidden">
              <DataTable columns={COLUMNS} rows={MOCK_CONTACTS} emptyLabel="No contacts yet." />
            </div>
          </>
        );
      }}
    </CompanyScopedPage>
  );
}
