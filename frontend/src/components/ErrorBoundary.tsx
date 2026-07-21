import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

/**
 * Catches render errors (and failed lazy-chunk loads) in the routed page so a
 * single broken page degrades gracefully instead of blanking the whole AI OS —
 * the shell (nav, dock, Core) stays usable and the user can navigate away.
 * Keyed by route in DashboardShell, so it auto-resets on navigation.
 */
export default class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface for debugging; no secrets are logged (just the error + stack).
    console.error("Page error boundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full border border-jarvis-amber/40 bg-jarvis-amber/10 text-jarvis-amber">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <div>
            <p className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
              THIS SCREEN HIT AN ERROR
            </p>
            <p className="mt-1 max-w-sm text-sm text-jarvis-muted">
              The rest of Jarvis is still running — use the navigation to switch to another screen, or
              reload this one.
            </p>
          </div>
          <button
            onClick={() => this.setState({ error: null })}
            className="press-scale rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-4 py-2 text-sm font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
