import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";

export interface PromptField {
  key: string;
  label: string;
  placeholder?: string;
  multiline?: boolean;
}

export interface PromptConfig {
  title: string;
  description?: string;
  fields: PromptField[];
  confirmLabel?: string;
}

type PromptResult = Record<string, string> | null;

interface PromptContextValue {
  prompt: (config: PromptConfig) => Promise<PromptResult>;
}

const PromptContext = createContext<PromptContextValue | undefined>(undefined);

// Replaces window.prompt() throughout the app. window.prompt/alert are
// blocking native dialogs that can hang the page (and in real Chrome usage
// get silently auto-suppressed after repeated use), and there's no way to
// distinguish "cancelled" from "submitted blank" without extra plumbing.
// This renders an in-app modal instead and resolves `null` on cancel so
// callers can actually tell the two apart.
export function PromptProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<PromptConfig | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const resolverRef = useRef<((result: PromptResult) => void) | null>(null);

  const prompt = useCallback((cfg: PromptConfig) => {
    return new Promise<PromptResult>((resolve) => {
      resolverRef.current = resolve;
      setValues(Object.fromEntries(cfg.fields.map((f) => [f.key, ""])));
      setConfig(cfg);
    });
  }, []);

  function close(result: PromptResult) {
    resolverRef.current?.(result);
    resolverRef.current = null;
    setConfig(null);
  }

  function handleConfirm() {
    close(values);
  }

  return (
    <PromptContext.Provider value={{ prompt }}>
      {children}
      <AnimatePresence>
        {config && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => close(null)}
              className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="hud-panel hud-corner fixed left-1/2 top-1/2 z-[70] w-full max-w-md -translate-x-1/2 -translate-y-1/2 p-6 shadow-elevated-lg"
            >
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleConfirm();
                }}
              >
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
                      {config.title}
                    </h2>
                    {config.description && (
                      <p className="mt-1 text-xs text-jarvis-muted">{config.description}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => close(null)}
                    className="press-scale shrink-0 rounded-lg p-1.5 text-jarvis-muted transition hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="flex flex-col gap-3">
                  {config.fields.map((field, i) => (
                    <label key={field.key} className="flex flex-col gap-1.5">
                      <span className="text-xs font-medium text-jarvis-muted">{field.label}</span>
                      {field.multiline ? (
                        <textarea
                          autoFocus={i === 0}
                          rows={3}
                          value={values[field.key] ?? ""}
                          onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
                          placeholder={field.placeholder}
                          className="resize-none rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3.5 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none"
                        />
                      ) : (
                        <input
                          autoFocus={i === 0}
                          value={values[field.key] ?? ""}
                          onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
                          placeholder={field.placeholder}
                          className="rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3.5 py-2.5 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none"
                        />
                      )}
                    </label>
                  ))}
                </div>

                <div className="mt-5 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => close(null)}
                    className="press-scale rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-4 py-2 text-sm font-medium text-jarvis-muted transition hover:text-jarvis-text"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="press-scale rounded-xl border border-jarvis-cyan/50 bg-jarvis-cyan/10 px-4 py-2 text-sm font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
                  >
                    {config.confirmLabel ?? "Continue"}
                  </button>
                </div>
              </form>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </PromptContext.Provider>
  );
}

export function usePrompt() {
  const ctx = useContext(PromptContext);
  if (!ctx) throw new Error("usePrompt must be used within a PromptProvider");
  return ctx.prompt;
}
