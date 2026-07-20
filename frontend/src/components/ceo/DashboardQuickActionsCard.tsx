import { useNavigate } from "react-router-dom";
import { BarChart3, Boxes, CalendarClock, Factory, Mail, Mic, Rocket } from "lucide-react";

import { useCompany } from "@/context/CompanyContext";

interface Action {
  key: string;
  label: string;
  icon: typeof Mail;
  run: (helpers: { navigate: ReturnType<typeof useNavigate>; focusPrimalPenni: () => void }) => void;
}

const ACTIONS: Action[] = [
  {
    key: "email",
    label: "Read my email",
    icon: Mail,
    run: ({ navigate }) => navigate("/chat?prompt=" + encodeURIComponent("Read my recent emails and summarize them.")),
  },
  {
    key: "calendar",
    label: "Show today's calendar",
    icon: CalendarClock,
    run: ({ navigate }) => navigate("/chat?prompt=" + encodeURIComponent("Show me today's calendar events.")),
  },
  {
    key: "launch",
    label: "Review launch progress",
    icon: Rocket,
    run: ({ navigate, focusPrimalPenni }) => {
      focusPrimalPenni();
      navigate("/company/dashboard");
    },
  },
  {
    key: "manufacturer",
    label: "Open manufacturer tracker",
    icon: Factory,
    run: ({ navigate, focusPrimalPenni }) => {
      focusPrimalPenni();
      navigate("/company/manufacturing-tracker");
    },
  },
  {
    key: "inventory",
    label: "Open inventory",
    icon: Boxes,
    run: ({ navigate }) => navigate("/company/inventory"),
  },
  {
    key: "finances",
    label: "Review finances",
    icon: BarChart3,
    run: ({ navigate }) => navigate("/company/financials"),
  },
  {
    key: "voice",
    label: "Start voice mode",
    icon: Mic,
    run: ({ navigate }) => navigate("/chat?voice=1"),
  },
];

export default function DashboardQuickActionsCard() {
  const navigate = useNavigate();
  const { companies, setActiveCompanyId } = useCompany();

  function focusPrimalPenni() {
    const match = companies.find((c) => c.name.toLowerCase().includes("primal penni"));
    if (match) setActiveCompanyId(match.id);
  }

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="border-b border-jarvis-border/60 px-5 py-4">
        <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">QUICK ACTIONS</h2>
      </div>
      <div className="grid flex-1 grid-cols-2 gap-2 p-4">
        {ACTIONS.map((action) => (
          <button
            key={action.key}
            onClick={() => action.run({ navigate, focusPrimalPenni })}
            className="press-scale flex flex-col items-start gap-1.5 rounded-xl border border-jarvis-border bg-jarvis-panel2/50 p-3 text-left transition-all duration-200 hover:border-jarvis-cyan/50 hover:bg-jarvis-cyan/10 hover:shadow-glow-sm"
          >
            <action.icon className="h-4 w-4 text-jarvis-cyan" />
            <span className="text-xs font-medium leading-tight text-jarvis-text">{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
