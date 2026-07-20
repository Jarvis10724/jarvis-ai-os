import { Globe } from "lucide-react";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import DataTable, { type DataTableColumn } from "@/components/DataTable";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill, { type StatusTone } from "@/components/StatusPill";
import { MOCK_PAGES, WEBSITE_STATUS_LABELS } from "@/mock/websiteBuilder";
import type { WebsitePage } from "@/types";

const STATUS_TONE: Record<WebsitePage["status"], StatusTone> = {
  planned: "neutral",
  drafting: "progress",
  live: "success",
};

const COLUMNS: DataTableColumn<WebsitePage>[] = [
  { key: "name", label: "Page", render: (p) => <span className="font-medium text-jarvis-text">{p.name}</span> },
  { key: "path", label: "Path", render: (p) => <code className="text-xs text-jarvis-muted">{p.path}</code> },
  { key: "status", label: "Status", render: (p) => <StatusPill label={WEBSITE_STATUS_LABELS[p.status]} tone={STATUS_TONE[p.status]} /> },
  { key: "lastEdited", label: "Last Edited", render: (p) => p.lastEdited ?? "—" },
];

export default function WebsiteBuilderPage() {
  return (
    <CompanyScopedPage>
      {(company) => (
        <>
          <ModulePageHeader
            icon={Globe}
            title="Website Builder"
            description={`Site structure and page status for ${company.name}.${company.website ? ` Live at ${company.website}.` : ""}`}
          />

          <div className="hud-panel hud-corner shrink-0 p-4 text-xs text-jarvis-muted">
            The real <code>web_builder</code> AI plugin already exists on the backend
            (<code>POST /api/v1/plugins/web_builder/run</code>) and can turn a brief into a page plan and
            starter HTML today via Quick Actions on the Overview page. This module tracks page-level status
            over time — that part is still mock until it has its own table.
          </div>

          <div className="hud-panel hud-corner min-h-0 flex-1 overflow-hidden">
            <DataTable columns={COLUMNS} rows={MOCK_PAGES} emptyLabel="No pages planned yet." />
          </div>
        </>
      )}
    </CompanyScopedPage>
  );
}
