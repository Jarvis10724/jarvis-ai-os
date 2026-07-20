/**
 * Structured workspace panels — the thing that turns each Quick Action into a
 * real studio instead of a chat box. Every panel renders the *real* AI-
 * generated `state` the backend merged from the model's `jarvis-state` block
 * (see app.core.workspace_actions). Nothing here is mock data: an empty panel
 * shows a "generate this" affordance that sends a stage-targeted prompt.
 */
import clsx from "clsx";
import {
  AlertTriangle,
  Check,
  CircleDot,
  Clock,
  Download,
  FileCode2,
  Image as ImageIcon,
  Layers,
  Loader2,
  Sparkles,
  Wand2,
} from "lucide-react";

import MarkdownLite from "@/components/MarkdownLite";
import type { WorkspaceDetail } from "@/types";

// --- context passed from Studio into the panels ---------------------------

export interface PanelCtx {
  actionKey: string;
  detail: WorkspaceDetail;
  imageConfigured: boolean;
  streaming: boolean;
  generatingImageFor: string | null;
  /** Send a stage-targeted message (drives the model to fill this panel). */
  onPrompt: (stage: string, prompt: string) => void;
  /** Generate a real image for a logo concept (no-op UI if unconfigured). */
  onGenerateImage: (conceptId: string | null, name: string, prompt: string) => void;
}

// --- safe readers ---------------------------------------------------------

const asArray = (v: unknown): Record<string, unknown>[] =>
  Array.isArray(v) ? (v as Record<string, unknown>[]) : [];
const asObj = (v: unknown): Record<string, unknown> =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
const asStr = (v: unknown): string => (typeof v === "string" ? v : v == null ? "" : String(v));

// --- shared primitives ----------------------------------------------------

function Empty({ hint, label, onGenerate }: { hint: string; label: string; onGenerate?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-jarvis-border/70 bg-jarvis-panel2/30 px-4 py-10 text-center">
      <Layers className="h-6 w-6 text-jarvis-muted" />
      <p className="max-w-xs text-xs text-jarvis-muted">{hint}</p>
      {onGenerate && (
        <button
          onClick={onGenerate}
          className="press-scale flex items-center gap-1.5 rounded-lg border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3 py-1.5 text-xs font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
        >
          <Wand2 className="h-3.5 w-3.5" />
          {label}
        </button>
      )}
    </div>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 p-3.5", className)}>
      {children}
    </div>
  );
}

function KeyVals({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="grid grid-cols-1 gap-2">
      {rows
        .filter(([, v]) => v)
        .map(([k, v]) => (
          <div key={k} className="flex flex-col gap-0.5">
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-jarvis-faint">{k}</dt>
            <dd className="text-sm text-jarvis-text">{v}</dd>
          </div>
        ))}
    </dl>
  );
}

function Chips({ items, tone = "cyan" }: { items: unknown[]; tone?: string }) {
  const list = items.map(asStr).filter(Boolean);
  if (!list.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {list.map((c, i) => (
        <span
          key={i}
          className={clsx(
            "rounded-full border px-2 py-0.5 text-[11px]",
            tone === "cyan"
              ? "border-jarvis-cyan/30 bg-jarvis-cyan/10 text-jarvis-cyan"
              : "border-jarvis-border/70 bg-jarvis-panel2/50 text-jarvis-muted"
          )}
        >
          {c}
        </span>
      ))}
    </div>
  );
}

function Palette({ palette }: { palette: unknown }) {
  const colors = asArray(palette);
  if (!colors.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {colors.map((c, i) => {
        const hex = asStr(c.hex);
        return (
          <div key={i} className="flex items-center gap-1.5 rounded-lg border border-jarvis-border/60 bg-jarvis-panel/50 px-2 py-1">
            <span className="h-4 w-4 rounded border border-black/20" style={{ backgroundColor: hex || "#334" }} />
            <span className="text-[10px] text-jarvis-muted">
              {asStr(c.name) || hex}{asStr(c.name) && hex ? ` · ${hex}` : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function CodeBlock({ language, content }: { language?: string; content: string }) {
  return (
    <pre className="max-h-72 overflow-auto rounded-lg border border-jarvis-border/60 bg-jarvis-bg/60 p-3 text-[11px] leading-relaxed text-jarvis-text">
      {language && <div className="mb-1 text-[9px] uppercase tracking-wider text-jarvis-faint">{language}</div>}
      <code>{content}</code>
    </pre>
  );
}

function Timeline({ items, render }: { items: Record<string, unknown>[]; render: (it: Record<string, unknown>) => React.ReactNode }) {
  return (
    <ol className="space-y-2">
      {items.map((it, i) => (
        <li key={i} className="flex gap-2.5">
          <div className="mt-1 flex flex-col items-center">
            <CircleDot className="h-3 w-3 text-jarvis-cyan" />
            {i < items.length - 1 && <span className="my-0.5 w-px flex-1 bg-jarvis-border/60" />}
          </div>
          <div className="flex-1 pb-1 text-xs text-jarvis-text">{render(it)}</div>
        </li>
      ))}
    </ol>
  );
}

function StatusDot({ status }: { status: string }) {
  const tone =
    status === "done" || status === "passing"
      ? "bg-jarvis-emerald"
      : status === "doing" || status === "in_progress"
        ? "bg-jarvis-amber"
        : status === "failing"
          ? "bg-jarvis-rose"
          : "bg-jarvis-muted";
  return <span className={clsx("h-2 w-2 shrink-0 rounded-full", tone)} />;
}

// A section wrapper with a title + optional generate button.
function Section({
  title,
  onGenerate,
  generateLabel,
  children,
}: {
  title: string;
  onGenerate?: () => void;
  generateLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-xs font-bold uppercase tracking-wider text-jarvis-text">{title}</h3>
        {onGenerate && (
          <button
            onClick={onGenerate}
            className="press-scale flex items-center gap-1 rounded-md border border-jarvis-border/70 px-2 py-1 text-[10px] font-semibold text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
          >
            <Sparkles className="h-3 w-3" /> {generateLabel ?? "Generate"}
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

// --- per-stage renderers --------------------------------------------------

function MarkdownState({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 p-3.5">
      <MarkdownLite content={text} />
    </div>
  );
}

/** The registry: (actionKey, stateKey) -> renderer. Falls back to markdown /
 * JSON so a new state key never renders blank. */
function renderContent(stateKey: string, value: unknown, ctx: PanelCtx): React.ReactNode {
  switch (stateKey) {
    // ---- Website ----
    case "sitemap": {
      const pages = asArray(value);
      return (
        <div className="space-y-2">
          {pages.map((p, i) => (
            <Card key={i}>
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-jarvis-text">{asStr(p.title) || asStr(p.path)}</p>
                <code className="text-[10px] text-jarvis-cyan">{asStr(p.path)}</code>
              </div>
              {asStr(p.purpose) && <p className="mt-0.5 text-xs text-jarvis-muted">{asStr(p.purpose)}</p>}
              <Chips items={asArray(p.sections).length ? (p.sections as unknown[]) : (Array.isArray(p.sections) ? [] : [])} tone="muted" />
            </Card>
          ))}
        </div>
      );
    }
    case "copy": {
      const obj = asObj(value);
      return (
        <div className="space-y-2">
          {Object.entries(obj).map(([path, v]) => {
            const page = asObj(v);
            return (
              <Card key={path}>
                <p className="mb-1 text-xs font-semibold text-jarvis-cyan">{path}</p>
                {asStr(page.heading) && <p className="text-sm font-semibold text-jarvis-text">{asStr(page.heading)}</p>}
                <div className="mt-1.5 space-y-1.5">
                  {asArray(page.sections).map((s, i) => (
                    <div key={i}>
                      {asStr(s.title) && <p className="text-[11px] font-semibold text-jarvis-text">{asStr(s.title)}</p>}
                      <p className="text-xs text-jarvis-muted">{asStr(s.body)}</p>
                    </div>
                  ))}
                </div>
              </Card>
            );
          })}
        </div>
      );
    }
    case "design": {
      const d = asObj(value);
      const typo = asObj(d.typography);
      return (
        <Card>
          <Palette palette={d.palette} />
          <div className="mt-2">
            <KeyVals rows={[["Heading", asStr(typo.heading)], ["Body", asStr(typo.body)]]} />
          </div>
          {asStr(d.style_notes) && <p className="mt-2 text-xs text-jarvis-muted">{asStr(d.style_notes)}</p>}
        </Card>
      );
    }
    case "code": {
      const files = asArray(asObj(value).files);
      return (
        <div className="space-y-2">
          {files.map((f, i) => (
            <Card key={i}>
              <div className="mb-1.5 flex items-center gap-1.5">
                <FileCode2 className="h-3.5 w-3.5 text-jarvis-cyan" />
                <code className="text-xs text-jarvis-text">{asStr(f.path)}</code>
              </div>
              <CodeBlock language={asStr(f.language)} content={asStr(f.content)} />
            </Card>
          ))}
        </div>
      );
    }
    case "preview_html": {
      const html = asStr(value);
      return (
        <div className="overflow-hidden rounded-xl border border-jarvis-border/70">
          <iframe
            title="Site preview"
            sandbox=""
            srcDoc={html}
            className="h-96 w-full bg-white"
          />
        </div>
      );
    }
    // ---- Logo ----
    case "brief": {
      const b = asObj(value);
      return (
        <Card>
          <KeyVals
            rows={[
              ["Brand", asStr(b.brand_name)],
              ["Audience", asStr(b.audience)],
              ["Tone", asStr(b.tone)],
            ]}
          />
          <div className="mt-2 space-y-1.5">
            <Chips items={asArray(b.values).length ? (b.values as unknown[]) : []} />
            <Chips items={asArray(b.keywords).length ? (b.keywords as unknown[]) : []} tone="muted" />
          </div>
        </Card>
      );
    }
    case "concepts": {
      const concepts = asArray(value);
      return (
        <div className="space-y-2.5">
          {concepts.map((c, i) => {
            const id = asStr(c.id) || `concept-${i}`;
            const prompt = asStr(c.image_prompt) || asStr(c.imagery);
            const busy = ctx.generatingImageFor === id;
            return (
              <Card key={i}>
                <p className="text-sm font-semibold text-jarvis-text">{asStr(c.name) || `Concept ${i + 1}`}</p>
                {asStr(c.idea) && <p className="mt-0.5 text-xs text-jarvis-muted">{asStr(c.idea)}</p>}
                {asStr(c.imagery) && <p className="mt-1 text-xs text-jarvis-text"><span className="text-jarvis-faint">Imagery: </span>{asStr(c.imagery)}</p>}
                <div className="mt-2"><Palette palette={c.palette} /></div>
                {asStr(c.typography) && <p className="mt-1.5 text-[11px] text-jarvis-muted">Type: {asStr(c.typography)}</p>}
                {asStr(c.rationale) && <p className="mt-1 text-[11px] italic text-jarvis-faint">{asStr(c.rationale)}</p>}
                <button
                  disabled={busy || ctx.streaming}
                  onClick={() => ctx.onGenerateImage(id, asStr(c.name) || `Concept ${i + 1}`, prompt)}
                  className="press-scale mt-2.5 flex items-center gap-1.5 rounded-lg border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-2.5 py-1.5 text-[11px] font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20 disabled:opacity-40"
                  title={ctx.imageConfigured ? "Generate a real image for this concept" : "Set OPENAI_API_KEY to enable image generation"}
                >
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImageIcon className="h-3.5 w-3.5" />}
                  {ctx.imageConfigured ? "Generate image" : "Image gen not configured"}
                </button>
              </Card>
            );
          })}
        </div>
      );
    }
    case "images": {
      // Images live in state.images (populated by the /image endpoint).
      const imgs = asArray(ctx.detail.state.images);
      if (!imgs.length) return null;
      return (
        <div className="grid grid-cols-2 gap-2">
          {imgs.map((im, i) => (
            <figure key={i} className="overflow-hidden rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40">
              <img src={asStr(im.data_url)} alt={asStr(im.name)} className="aspect-square w-full object-contain bg-white/5" />
              <figcaption className="truncate px-2 py-1 text-[10px] text-jarvis-muted">{asStr(im.name)}</figcaption>
            </figure>
          ))}
        </div>
      );
    }
    case "revisions":
    case "progress":
    case "activity":
    case "test_runs": {
      const items = asArray(value);
      return (
        <Timeline
          items={items}
          render={(it) => (
            <div>
              <span className="text-jarvis-text">{asStr(it.note) || asStr(it.event) || asStr(it.outcome)}</span>
              {asStr(it.input) && <span className="text-jarvis-faint"> · in: {asStr(it.input)}</span>}
            </div>
          )}
        />
      );
    }
    case "exports": {
      const exps = asArray(value);
      return (
        <div className="space-y-2">
          {exps.map((e, i) => (
            <Card key={i} className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-jarvis-text">{asStr(e.name)}</p>
                <Chips items={asArray(e.formats).length ? (e.formats as unknown[]) : []} tone="muted" />
              </div>
              <Download className="h-4 w-4 text-jarvis-muted" />
            </Card>
          ))}
        </div>
      );
    }
    // ---- Product ----
    case "positioning": {
      const p = asObj(value);
      return (
        <Card>
          <KeyVals
            rows={[
              ["Target customer", asStr(p.target_customer)],
              ["Market", asStr(p.market)],
              ["Differentiation", asStr(p.differentiation)],
            ]}
          />
          <div className="mt-2"><Chips items={asArray(p.competitors).length ? (p.competitors as unknown[]) : []} tone="muted" /></div>
        </Card>
      );
    }
    case "spec": {
      const s = asObj(value);
      const specs = asArray(s.specifications);
      return (
        <Card>
          {asStr(s.summary) && <p className="mb-2 text-xs text-jarvis-muted">{asStr(s.summary)}</p>}
          <div className="space-y-1">
            {specs.map((sp, i) => (
              <div key={i} className="flex justify-between border-b border-jarvis-border/40 py-1 text-xs last:border-0">
                <span className="text-jarvis-faint">{asStr(sp.name)}</span>
                <span className="text-jarvis-text">{asStr(sp.value)}</span>
              </div>
            ))}
          </div>
        </Card>
      );
    }
    case "pricing": {
      const p = asObj(value);
      const tiers = asArray(p.tiers);
      return (
        <Card>
          <div className="grid grid-cols-3 gap-2 text-center">
            <Stat label="Unit cost" value={asStr(p.unit_cost)} />
            <Stat label="Price" value={asStr(p.price)} />
            <Stat label="Margin" value={asStr(p.margin_pct) ? `${asStr(p.margin_pct)}%` : ""} />
          </div>
          {tiers.length > 0 && (
            <div className="mt-2 space-y-1">
              {tiers.map((t, i) => (
                <div key={i} className="flex justify-between text-xs">
                  <span className="text-jarvis-text">{asStr(t.name)}</span>
                  <span className="text-jarvis-cyan">{asStr(t.price)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      );
    }
    case "manufacturing": {
      const m = asObj(value);
      return (
        <Card>
          <ul className="mb-2 space-y-1">
            {asArray(m.requirements).map((r, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-jarvis-text">
                <Check className="mt-0.5 h-3 w-3 shrink-0 text-jarvis-cyan" />
                {asStr(r)}
              </li>
            ))}
          </ul>
          <KeyVals rows={[["MOQ", asStr(m.moq)], ["Lead time", asStr(m.lead_time)], ["Notes", asStr(m.notes)]]} />
        </Card>
      );
    }
    case "launch_checklist": {
      const items = asArray(value);
      return (
        <div className="space-y-1.5">
          {items.map((it, i) => (
            <Card key={i} className="flex items-center gap-2">
              <span className={clsx("flex h-4 w-4 items-center justify-center rounded border", it.done ? "border-jarvis-emerald bg-jarvis-emerald/20" : "border-jarvis-border")}>
                {it.done ? <Check className="h-3 w-3 text-jarvis-emerald" /> : null}
              </span>
              <span className="flex-1 text-xs text-jarvis-text">{asStr(it.item)}</span>
              {asStr(it.owner) && <span className="text-[10px] text-jarvis-faint">{asStr(it.owner)}</span>}
            </Card>
          ))}
        </div>
      );
    }
    // ---- Research ----
    case "plan": {
      const steps = asArray(value);
      return (
        <ol className="space-y-1.5">
          {steps.map((s, i) => (
            <li key={i} className="flex items-center gap-2 rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 px-3 py-2 text-xs">
              <StatusDot status={asStr(s.status)} />
              <span className="flex-1 text-jarvis-text">{asStr(s.step)}</span>
              <span className="text-[10px] uppercase text-jarvis-faint">{asStr(s.status)}</span>
            </li>
          ))}
        </ol>
      );
    }
    case "sources": {
      const sources = asArray(value);
      return (
        <div className="space-y-2">
          {sources.map((s, i) => (
            <Card key={i}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-semibold text-jarvis-text">{asStr(s.title)}</p>
                {s.derived ? (
                  <span className="shrink-0 rounded-full border border-jarvis-amber/40 bg-jarvis-amber/10 px-2 py-0.5 text-[9px] font-semibold uppercase text-jarvis-amber">
                    Derived
                  </span>
                ) : null}
              </div>
              {asStr(s.note) && <p className="mt-0.5 text-xs text-jarvis-muted">{asStr(s.note)}</p>}
              {asStr(s.url) && <p className="mt-1 truncate text-[10px] text-jarvis-cyan">{asStr(s.url)}</p>}
            </Card>
          ))}
        </div>
      );
    }
    case "citations": {
      const cites = asArray(value);
      return (
        <div className="space-y-1.5">
          {cites.map((c, i) => (
            <Card key={i}>
              <p className="text-xs text-jarvis-text">{asStr(c.claim)}</p>
              <p className="mt-0.5 text-[10px] text-jarvis-faint">source: {asStr(c.source_id)}</p>
            </Card>
          ))}
        </div>
      );
    }
    // ---- Code ----
    case "file_tree": {
      const tree = asArray(value).map(asStr).length ? (value as unknown[]).map(asStr) : [];
      return (
        <Card>
          <pre className="text-[11px] leading-relaxed text-jarvis-text">
            {tree.map((p, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <FileCode2 className="h-3 w-3 text-jarvis-faint" />
                {p}
              </div>
            ))}
          </pre>
        </Card>
      );
    }
    case "files": {
      const files = asArray(value);
      return (
        <div className="space-y-2">
          {files.map((f, i) => (
            <Card key={i}>
              <code className="mb-1 block text-xs text-jarvis-cyan">{asStr(f.path)}</code>
              <CodeBlock language={asStr(f.language)} content={asStr(f.content)} />
            </Card>
          ))}
        </div>
      );
    }
    case "test_status": {
      const t = asObj(value);
      const cases = asArray(t.cases);
      return (
        <Card>
          <div className="flex items-center gap-2">
            <StatusDot status={asStr(t.status)} />
            <span className="text-sm font-semibold text-jarvis-text">{asStr(t.status) || "unknown"}</span>
            <span className="text-[10px] text-jarvis-faint">{asStr(t.framework)}</span>
          </div>
          {asStr(t.summary) && <p className="mt-1 text-xs text-jarvis-muted">{asStr(t.summary)}</p>}
          <div className="mt-2 space-y-1">
            {cases.map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <StatusDot status={asStr(c.status)} />
                <span className="text-jarvis-text">{asStr(c.name)}</span>
              </div>
            ))}
          </div>
        </Card>
      );
    }
    // ---- Automation ----
    case "trigger": {
      const t = asObj(value);
      return <Card><KeyVals rows={[["Type", asStr(t.type)], ["Detail", asStr(t.detail)]]} /></Card>;
    }
    case "actions": {
      const actions = asArray(value);
      return (
        <ol className="space-y-1.5">
          {actions.map((a, i) => (
            <li key={i} className="flex items-start gap-2 rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 px-3 py-2">
              <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-jarvis-cyan/20 text-[9px] font-bold text-jarvis-cyan">
                {asStr(a.order) || i + 1}
              </span>
              <div className="flex-1">
                <p className="text-xs font-medium text-jarvis-text">{asStr(a.action)}</p>
                {asStr(a.tool) && <p className="text-[10px] text-jarvis-faint">{asStr(a.tool)}</p>}
              </div>
              {a.requires_approval ? (
                <span className="shrink-0 rounded-full border border-jarvis-amber/40 bg-jarvis-amber/10 px-2 py-0.5 text-[9px] font-semibold uppercase text-jarvis-amber">
                  Approval
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      );
    }
    case "conditions": {
      const conds = asArray(value);
      return (
        <div className="space-y-1.5">
          {conds.map((c, i) => (
            <Card key={i} className="text-xs">
              <span className="text-jarvis-faint">When </span>
              <span className="text-jarvis-text">{asStr(c.when)}</span>
              <span className="text-jarvis-faint"> → then </span>
              <span className="text-jarvis-cyan">{asStr(c.then)}</span>
            </Card>
          ))}
        </div>
      );
    }
    // ---- Fallbacks ----
    default:
      if (typeof value === "string") return <MarkdownState text={value} />;
      return (
        <Card>
          <pre className="overflow-auto text-[11px] text-jarvis-muted">{JSON.stringify(value, null, 2)}</pre>
        </Card>
      );
  }
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-jarvis-border/60 bg-jarvis-panel/50 py-2">
      <p className="text-[9px] uppercase tracking-wide text-jarvis-faint">{label}</p>
      <p className="text-sm font-semibold text-jarvis-text">{value || "—"}</p>
    </div>
  );
}

// Renders one stage's panel: header + content or an empty-state generate CTA.
export function StagePanel({
  stateKey,
  label,
  hint,
  ctx,
}: {
  stateKey: string;
  label: string;
  hint: string;
  ctx: PanelCtx;
}) {
  const value = ctx.detail.state[stateKey];
  const hasValue =
    stateKey === "images"
      ? asArray(ctx.detail.state.images).length > 0
      : Array.isArray(value)
        ? value.length > 0
        : value && typeof value === "object"
          ? Object.keys(value).length > 0
          : Boolean(asStr(value).trim());

  const generatePrompt = `Work on the ${label} stage. ${hint}. Produce it now and update the workspace state.`;

  return (
    <Section
      title={label}
      onGenerate={hasValue && stateKey !== "images" ? () => ctx.onPrompt(stateKey, generatePrompt) : undefined}
      generateLabel="Refine"
    >
      {hasValue ? (
        renderContent(stateKey, value, ctx)
      ) : (
        <Empty
          hint={hint || `This panel fills in as ${ctx.detail.action_label} produces the ${label.toLowerCase()}.`}
          label={`Generate ${label}`}
          onGenerate={stateKey === "images" ? undefined : () => ctx.onPrompt(stateKey, generatePrompt)}
        />
      )}
    </Section>
  );
}

// Small header shown for the Automation "enabled / requires approval" state.
export function AutomationBanner({ ctx }: { ctx: PanelCtx }) {
  const enabled = Boolean(ctx.detail.state.enabled);
  const approval = Boolean(ctx.detail.state.requires_approval);
  return (
    <div className="flex items-center gap-2 rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 px-3 py-2">
      <span
        className={clsx(
          "flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
          enabled ? "bg-jarvis-emerald/15 text-jarvis-emerald" : "bg-jarvis-panel2 text-jarvis-muted"
        )}
      >
        <Clock className="h-3 w-3" /> {enabled ? "Enabled" : "Disabled"}
      </span>
      {approval && (
        <span className="flex items-center gap-1 rounded-full bg-jarvis-amber/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-jarvis-amber">
          <AlertTriangle className="h-3 w-3" /> Approval required
        </span>
      )}
    </div>
  );
}

export { asArray };
export type { WorkspaceDetail };
