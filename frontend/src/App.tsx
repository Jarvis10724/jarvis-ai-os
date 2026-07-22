import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";
import DashboardShell from "@/components/DashboardShell";
// Login is eager (pre-auth entry, first paint); the shell is eager (it's the
// persistent chrome). Every routed page is code-split so the initial bundle
// stays small and each workspace module loads on demand — this scales as more
// modules/workspaces are added.
import Login from "@/pages/Login";

const ApprovalsPage = lazy(() => import("@/pages/Approvals"));
const AutomationPage = lazy(() => import("@/pages/Automation"));
const ChatPage = lazy(() => import("@/pages/Chat"));
const IntegrationsPage = lazy(() => import("@/pages/Integrations"));
const PluginsPage = lazy(() => import("@/pages/Plugins"));
const SettingsPage = lazy(() => import("@/pages/Settings"));
const AmazonLaunchCenterPage = lazy(() => import("@/pages/company/AmazonLaunch"));
const BrandBrainPage = lazy(() => import("@/pages/company/BrandBrain"));
const CompanyDashboardPage = lazy(() => import("@/pages/company/CompanyDashboard"));
const ContentCalendarPage = lazy(() => import("@/pages/company/ContentCalendar"));
const CrmPage = lazy(() => import("@/pages/company/Crm"));
const FinancialDashboardPage = lazy(() => import("@/pages/company/Financials"));
const InventoryPage = lazy(() => import("@/pages/company/Inventory"));
const ManufacturingTrackerPage = lazy(() => import("@/pages/company/Manufacturing"));
const MarketingStudioPage = lazy(() => import("@/pages/company/MarketingStudio"));
const ProjectManagerPage = lazy(() => import("@/pages/company/Projects"));
const SopLibraryPage = lazy(() => import("@/pages/company/Sops"));
const WebsiteBuilderPage = lazy(() => import("@/pages/company/WebsiteBuilder"));
const CompanyProfile = lazy(() => import("@/pages/CompanyProfile"));
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const DailyBriefPage = lazy(() => import("@/pages/DailyBrief"));
const BusinessIdeaIncubatorPage = lazy(() => import("@/pages/Ideas"));
const InvestmentDashboardPage = lazy(() => import("@/pages/Investments"));
const MemoryPage = lazy(() => import("@/pages/Memory"));
const ProjectWorkspacePage = lazy(() => import("@/pages/ProjectWorkspace"));
const StudioPage = lazy(() => import("@/pages/Studio"));

// Single auth gate + shell for the whole authenticated route tree, instead
// of every route wrapping itself individually. DashboardShell renders once
// and stays mounted across navigations; only its <Outlet/> (this component's
// child route) swaps and transitions per page.
function ProtectedShell() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-jarvis-bg">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-jarvis-cyan/30 border-t-jarvis-cyan" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  return <DashboardShell />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedShell />}>
        <Route path="/company" element={<CompanyProfile />} />
        <Route path="/company/dashboard" element={<CompanyDashboardPage />} />
        <Route path="/company/projects" element={<ProjectManagerPage />} />
        <Route path="/company/crm" element={<CrmPage />} />
        <Route path="/company/sops" element={<SopLibraryPage />} />
        <Route path="/company/manufacturing-tracker" element={<ManufacturingTrackerPage />} />
        <Route path="/company/inventory" element={<InventoryPage />} />
        <Route path="/company/financials" element={<FinancialDashboardPage />} />
        <Route path="/company/marketing-studio" element={<MarketingStudioPage />} />
        <Route path="/company/content-calendar" element={<ContentCalendarPage />} />
        <Route path="/company/website-builder" element={<WebsiteBuilderPage />} />
        <Route path="/company/amazon-launch" element={<AmazonLaunchCenterPage />} />
        <Route path="/company/brand-brain" element={<BrandBrainPage />} />
        <Route path="/daily-brief" element={<DailyBriefPage />} />
        <Route path="/investments" element={<InvestmentDashboardPage />} />
        <Route path="/ideas" element={<BusinessIdeaIncubatorPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/projects/:id" element={<ProjectWorkspacePage />} />
        <Route path="/studio/:action" element={<StudioPage />} />
        <Route path="/memory" element={<MemoryPage />} />
        <Route path="/plugins" element={<PluginsPage />} />
        <Route path="/automation" element={<AutomationPage />} />
        <Route path="/integrations" element={<IntegrationsPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/*" element={<Dashboard />} />
      </Route>
    </Routes>
  );
}
