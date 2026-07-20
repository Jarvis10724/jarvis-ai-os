import { useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

import type { ChecklistItem } from "@/types";

export default function ChecklistCard({
  title,
  description,
  items,
  onSave,
}: {
  title: string;
  description?: string;
  items: ChecklistItem[];
  onSave: (items: ChecklistItem[]) => Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const doneCount = items.filter((i) => i.done).length;

  async function commit(next: ChecklistItem[]) {
    setSaving(true);
    try {
      await onSave(next);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1000);
    } finally {
      setSaving(false);
    }
  }

  function toggle(id: string) {
    commit(items.map((i) => (i.id === id ? { ...i, done: !i.done } : i)));
  }

  function updateNotes(id: string, notes: string) {
    commit(items.map((i) => (i.id === id ? { ...i, notes } : i)));
  }

  return (
    <div className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-jarvis-text">{title}</h3>
          {description && <p className="text-xs text-jarvis-muted">{description}</p>}
        </div>
        <div className="flex items-center gap-2 text-xs text-jarvis-muted">
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {savedFlash && !saving && <Check className="h-3.5 w-3.5 text-jarvis-emerald" />}
          <span className="font-data">
            {doneCount}/{items.length}
          </span>
        </div>
      </div>

      <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-jarvis-border/50">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-jarvis-cyan to-jarvis-emerald"
          animate={{ width: `${items.length ? (doneCount / items.length) * 100 : 0}%` }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>

      <ul className="space-y-1">
        {items.map((item, i) => (
          <motion.li
            key={item.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.02 * i, duration: 0.25 }}
            className="flex items-start gap-3 rounded-lg px-2 py-1.5 transition-colors duration-150 hover:bg-jarvis-panel2/50"
          >
            <button
              onClick={() => toggle(item.id)}
              className={clsx(
                "press-scale mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors duration-150",
                item.done
                  ? "border-jarvis-emerald bg-jarvis-emerald/20 text-jarvis-emerald"
                  : "border-jarvis-border text-transparent hover:border-jarvis-cyan/50"
              )}
            >
              <Check className="h-3 w-3" />
            </button>
            <div className="min-w-0 flex-1">
              <p
                className={clsx(
                  "text-sm leading-snug transition-colors duration-200",
                  item.done ? "text-jarvis-muted line-through" : "text-jarvis-text"
                )}
              >
                {item.label}
              </p>
              <input
                defaultValue={item.notes}
                placeholder="Add a note..."
                onBlur={(e) => {
                  if (e.target.value !== item.notes) updateNotes(item.id, e.target.value);
                }}
                className="mt-1 w-full rounded-md border border-transparent bg-transparent px-1.5 py-0.5 text-xs text-jarvis-muted placeholder:text-jarvis-faint transition-colors duration-150 hover:border-jarvis-border/60 focus:border-jarvis-cyan/40 focus:bg-jarvis-panel/60 focus:outline-none"
              />
            </div>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}
