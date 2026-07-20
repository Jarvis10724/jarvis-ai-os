import { Link } from "react-router-dom";
import {
  BookOpen,
  Boxes,
  DollarSign,
  Factory,
  Globe,
  LayoutDashboard,
  Megaphone,
  PackageSearch,
  Rocket,
  Users,
} from "lucide-react";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill from "@/components/StatusPill";
import { MOCK_CONTACTS } from "@/mock/crm";
import { MOCK_FINANCIAL_SUMMARY } from "@/mock/financials";
import { MOCK_INVENTORY } from "@/mock/inventory";
import { MOCK_PRODUCTION_RUNS } from "@/mock/manufacturing";
import { MOCK_PROJECTS } from "@/mock/projects";

const MODULE_LINKS = [
  { to: "/company/projects", label: "Project Manager", icon: Rocket },
  { to: "/company/crm", label: "CRM", icon: Users },
  { to: "/company/sops", label: "SOP Library", icon: BookOpen },
  { to: "/company/manufacturing-tracker", label: "Manufacturing Tracker", icon: Factory },
  { to: "/company/inventory", label: "Inventory", icon: Boxes },
  { to: "/company/financials", label: "Financial Dashboard", icon: DollarSign },
  { to: "/company/marketing-studio", label: "AI Marketing Studio", icon: Megaphone },
  { to: "/company/website-builder", label: "Website Builder", icon: Globe },
  { to: "/company/amazon-launch", label: "Amazon Launch Center", icon: PackageSearch },
];

export default function CompanyDashboardPage() {
  return (
    <CompanyScopedPage>
      {(company) => {
        const openProjects = MOCK_PROJECTS.filter((p) => p.status !== "done").length;
        const openPipeline = MOCK_CONTACTS.filter((c) => c.stage === "proposal" || c.stage === "contacted").length;
        const lowStock = MOCK_INVENTORY.filter((i) => i.onHand <= i.reorderPoint).length;
        const activeRuns = MOCK_PRODUCTION_RUNS.filter((r) => r.stage !== "complete").length;

        return (
          <>
            <ModulePageHeader
              icon={LayoutDashboard}
              title="Company Dashboard"
              description={`Operational snapshot for ${company.name}.${
                company.divisions.length ? ` Divisions: ${company.divisions.join(", ")}.` : ""
              }`}
            />

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="hud-panel p-4">
                <p className="text-xs text-jarvis-muted">Open Projects</p>
                <p className="mt-1 font-display text-xl font-bold text-jarvis-text">{openProjects}</p>
              </div>
              <div className="hud-panel p-4">
                <p className="text-xs text-jarvis-muted">Pipeline Contacts</p>
                <p className="mt-1 font-display text-xl font-bold text-jarvis-text">{openPipeline}</p>
              </div>
              <div className="hud-panel p-4">
                <p className="text-xs text-jarvis-muted">Cash on Hand</p>
                <p className="mt-1 font-display text-xl font-bold text-jarvis-cyan">
                  ${MOCK_FINANCIAL_SUMMARY.cashOnHand.toLocaleString()}
                </p>
              </div>
              <div className="hud-panel p-4">
                <p className="text-xs text-jarvis-muted">Active Production Runs</p>
                <p className="mt-1 font-display text-xl font-bold text-jarvis-text">{activeRuns}</p>
              </div>
            </div>

            {lowStock > 0 && (
              <div className="hud-panel flex items-center justify-between p-4">
                <p className="text-sm text-jarvis-text">
                  {lowStock} inventory item{lowStock > 1 ? "s" : ""} at or below reorder point.
                </p>
                <Link to="/company/inventory">
                  <StatusPill label="Review Inventory" tone="progress" />
                </Link>
              </div>
            )}

            <div className="hud-panel hud-corner min-h-0 flex-1 overflow-y-auto p-4">
              <p className="mb-3 text-xs uppercase tracking-wide text-jarvis-muted">Modules</p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {MODULE_LINKS.map(({ to, label, icon: Icon }) => (
                  <Link
                    key={to}
                    to={to}
                    className="flex items-center gap-3 rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 p-4 transition hover:border-jarvis-cyan/40 hover:bg-jarvis-cyan/5"
                  >
                    <Icon className="h-5 w-5 shrink-0 text-jarvis-cyan" />
                    <span className="text-sm font-medium text-jarvis-text">{label}</span>
                  </Link>
                ))}
              </div>
            </div>
          </>
        );
      }}
    </CompanyScopedPage>
  );
}
