import type { ReactNode } from "react";
import { RefreshCw, X } from "lucide-react";
import clsx from "clsx";

/**
 * Shared chrome for every right-dock panel: a titled header (with optional
 * refresh + a close affordance) over a scrolling body. Keeps all four panels
 * (Notifications, Timeline, Memory, Agents) visually identical to each other
 * and consistent with the rest of the HUD.
 */
export default function PanelFrame({
  title,
  icon: Icon,
  onClose,
  onRefresh,
  refreshing,
  subtitle,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  onClose: () => void;
  onRefresh?: () => void;
  refreshing?: boolean;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-jarvis-border/60 px-4 py-3">
        <Icon className="h-4 w-4 shrink-0 text-jarvis-cyan" />
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-display text-xs font-semibold tracking-widest text-jarvis-text">
            {title.toUpperCase()}
          </h2>
          {subtitle && <p className="truncate text-[11px] text-jarvis-muted">{subtitle}</p>}
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            title="Refresh"
            className="press-scale rounded-lg p-1.5 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-cyan"
          >
            <RefreshCw className={clsx("h-3.5 w-3.5", refreshing && "animate-spin")} />
          </button>
        )}
        <button
          onClick={onClose}
          title="Close panel"
          className="press-scale rounded-lg p-1.5 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
    </div>
  );
}

export function PanelEmpty({ label }: { label: string }) {
  return <p className="py-10 text-center text-sm text-jarvis-muted">{label}</p>;
}

export function PanelError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <p className="text-sm text-jarvis-muted">Couldn't load this panel.</p>
      <button
        onClick={onRetry}
        className="press-scale rounded-lg border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3 py-1.5 text-xs font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
      >
        Retry
      </button>
    </div>
  );
}

export function PanelLoading() {
  return (
    <div className="space-y-2">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="skeleton h-14 rounded-xl" />
      ))}
    </div>
  );
}
