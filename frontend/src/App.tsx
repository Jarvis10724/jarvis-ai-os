import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";
import DashboardShell from "@/components/DashboardShell";
import ApprovalsPage from "@/pages/Approvals";
import AutomationPage from "@/pages/Automation";
import ChatPage from "@/pages/Chat";
import IntegrationsPage from "@/pages/Integrations";
import PluginsPage from "@/pages/Plugins";
import SettingsPage from "@/pages/Settings";
import AmazonLaunchCenterPage from "@/pages/company/AmazonLaunch";
import CompanyDashboardPage from "@/pages/company/CompanyDashboard";
import ContentCalendarPage from "@/pages/company/ContentCalendar";
import CrmPage from "@/pages/company/Crm";
import FinancialDashboardPage from "@/pages/company/Financials";
import InventoryPage from "@/pages/company/Inventory";
import ManufacturingTrackerPage from "@/pages/company/Manufacturing";
import MarketingStudioPage from "@/pages/company/MarketingStudio";
import ProjectManagerPage from "@/pages/company/Projects";
import SopLibraryPage from "@/pages/company/Sops";
import WebsiteBuilderPage from "@/pages/company/WebsiteBuilder";
import CompanyProfile from "@/pages/CompanyProfile";
import Dashboard from "@/pages/Dashboard";
import DailyBriefPage from "@/pages/DailyBrief";
import BusinessIdeaIncubatorPage from "@/pages/Ideas";
import InvestmentDashboardPage from "@/pages/Investments";
import Login from "@/pages/Login";
import MemoryPage from "@/pages/Memory";
import ProjectWorkspacePage from "@/pages/ProjectWorkspace";
import StudioPage from "@/pages/Studio";

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
