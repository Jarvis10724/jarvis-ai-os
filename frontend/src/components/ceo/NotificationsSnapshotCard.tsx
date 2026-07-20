import { Bell } from "lucide-react";
import clsx from "clsx";

import SampleDataBadge from "@/components/SampleDataBadge";
import { NOTIFICATIONS, SEVERITY_ICON, SEVERITY_STYLES } from "@/components/NotificationsPanel";
import { useDashboardUI } from "@/context/DashboardUIContext";

export default function NotificationsSnapshotCard() {
  const { openNotifications } = useDashboardUI();
  const top = NOTIFICATIONS.slice(0, 3);

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Bell className="h-4 w-4 text-jarvis-cyan" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">NOTIFICATIONS</h2>
        </div>
        <SampleDataBadge />
      </div>
      <ul className="flex-1 space-y-2 overflow-y-auto p-4">
        {top.map((n) => {
          const Icon = SEVERITY_ICON[n.severity];
          return (
            <li
              key={n.id}
              className={clsx(
                "flex items-start gap-2.5 rounded-xl border px-3 py-2 text-xs",
                n.read ? "border-jarvis-border/40 bg-jarvis-panel2/25" : "border-jarvis-border/70 bg-jarvis-panel2/50"
              )}
            >
              <span className={clsx("mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border", SEVERITY_STYLES[n.severity])}>
                <Icon className="h-3 w-3" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-jarvis-text">{n.title}</p>
                <p className="text-[10px] text-jarvis-faint">{n.time}</p>
              </div>
            </li>
          );
        })}
      </ul>
      <button
        onClick={openNotifications}
        className="press-scale border-t border-jarvis-border/60 px-4 py-2.5 text-xs font-medium text-jarvis-cyan hover:bg-jarvis-panel2/40"
      >
        View all →
      </button>
    </div>
  );
}
