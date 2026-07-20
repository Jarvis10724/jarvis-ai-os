import { useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import { useToast } from "@/context/ToastContext";
import type { Product } from "@/types";

const LAUNCH_STATUSES = [
  "planning",
  "sourcing",
  "sampling",
  "manufacturing",
  "in_transit",
  "ready",
  "launched",
];

const STATUS_STYLES: Record<string, string> = {
  planning: "border-jarvis-muted/40 bg-jarvis-muted/10 text-jarvis-muted",
  sourcing: "border-jarvis-blue/40 bg-jarvis-blue/10 text-jarvis-blue",
  sampling: "border-jarvis-blue/40 bg-jarvis-blue/10 text-jarvis-blue",
  manufacturing: "border-jarvis-amber/40 bg-jarvis-amber/10 text-jarvis-amber",
  in_transit: "border-jarvis-amber/40 bg-jarvis-amber/10 text-jarvis-amber",
  ready: "border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan",
  launched: "border-jarvis-emerald/40 bg-jarvis-emerald/10 text-jarvis-emerald",
};

const INPUT_CLASS =
  "w-full rounded-lg border border-transparent bg-transparent px-2 py-1.5 text-jarvis-text placeholder:text-jarvis-faint transition-colors duration-150 hover:border-jarvis-border focus:border-jarvis-cyan/50 focus:bg-jarvis-panel2/70 focus:outline-none";
const NUM_INPUT_CLASS =
  "font-data w-full rounded-lg border border-transparent bg-transparent px-1 py-1.5 text-jarvis-text placeholder:text-jarvis-faint transition-colors duration-150 hover:border-jarvis-border focus:border-jarvis-cyan/50 focus:bg-jarvis-panel2/70 focus:outline-none";

export default function LaunchDashboard({
  companyId,
  products,
  onChange,
}: {
  companyId: string;
  products: Product[];
  onChange: (products: Product[]) => void;
}) {
  const [savingId, setSavingId] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [errorId, setErrorId] = useState<string | null>(null);
  const toast = useToast();

  async function saveField(product: Product, field: keyof Product, value: string) {
    let parsed: string | number | null = value;
    if (["cogs", "freight", "price", "margin"].includes(field as string)) {
      parsed = value === "" ? null : Number(value);
    } else if (["moq", "inventory"].includes(field as string)) {
      parsed = value === "" ? null : parseInt(value, 10);
    } else if (value === "") {
      parsed = null;
    }

    const next = products.map((p) => (p.id === product.id ? { ...p, [field]: parsed } : p));
    onChange(next);

    setSavingId(product.id);
    setErrorId(null);
    try {
      const updated = await api.updateProduct(companyId, product.id, { [field]: parsed });
      onChange(products.map((p) => (p.id === product.id ? updated : p)));
      setSavedId(product.id);
      setTimeout(() => setSavedId((cur) => (cur === product.id ? null : cur)), 1200);
    } catch (err) {
      setErrorId(product.id);
      toast.push(
        err instanceof ApiError ? `Failed to save: ${err.message}` : "Failed to save change.",
        "error"
      );
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between px-1 pb-3">
        <div>
          <h3 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
            LAUNCH DASHBOARD
          </h3>
          <p className="text-xs text-jarvis-muted">
            Real product tracking — fields start empty and are saved as they're entered.
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto rounded-xl border border-jarvis-border/60">
        <table className="w-full min-w-[1100px] border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-jarvis-panel2/95 shadow-[0_1px_0_0_theme(colors.jarvis.border)] backdrop-blur-xl">
            <tr className="text-left text-[11px] uppercase tracking-wide text-jarvis-muted">
              <th className="px-3 py-2.5 font-medium">Product</th>
              <th className="px-3 py-2.5 font-medium">Manufacturer</th>
              <th className="px-3 py-2.5 font-medium">Packaging</th>
              <th className="px-3 py-2.5 font-medium">MOQ</th>
              <th className="px-3 py-2.5 font-medium">COGS</th>
              <th className="px-3 py-2.5 font-medium">Freight</th>
              <th className="px-3 py-2.5 font-medium">Price</th>
              <th className="px-3 py-2.5 font-medium">Margin %</th>
              <th className="px-3 py-2.5 font-medium">Inventory</th>
              <th className="px-3 py-2.5 font-medium">Launch Status</th>
              <th className="w-8 px-3 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {products.map((product, i) => (
              <motion.tr
                key={product.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.03 * i, duration: 0.25 }}
                className="border-t border-jarvis-border/40 transition-colors duration-150 hover:bg-jarvis-panel2/30"
              >
                <td className="px-3 py-2">
                  <input
                    defaultValue={product.name}
                    onBlur={(e) => saveField(product, "name", e.target.value)}
                    className={clsx(INPUT_CLASS, "w-32")}
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    defaultValue={product.manufacturer ?? ""}
                    placeholder="TBD"
                    onBlur={(e) => saveField(product, "manufacturer", e.target.value)}
                    className={clsx(INPUT_CLASS, "w-32")}
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    defaultValue={product.packaging ?? ""}
                    placeholder="TBD"
                    onBlur={(e) => saveField(product, "packaging", e.target.value)}
                    className={clsx(INPUT_CLASS, "w-28")}
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    defaultValue={product.moq ?? ""}
                    placeholder="—"
                    onBlur={(e) => saveField(product, "moq", e.target.value)}
                    className={clsx(NUM_INPUT_CLASS, "w-20")}
                  />
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1">
                    <span className="font-data text-jarvis-faint">$</span>
                    <input
                      type="number"
                      step="0.01"
                      defaultValue={product.cogs ?? ""}
                      placeholder="—"
                      onBlur={(e) => saveField(product, "cogs", e.target.value)}
                      className={clsx(NUM_INPUT_CLASS, "w-20")}
                    />
                  </div>
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1">
                    <span className="font-data text-jarvis-faint">$</span>
                    <input
                      type="number"
                      step="0.01"
                      defaultValue={product.freight ?? ""}
                      placeholder="—"
                      onBlur={(e) => saveField(product, "freight", e.target.value)}
                      className={clsx(NUM_INPUT_CLASS, "w-20")}
                    />
                  </div>
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1">
                    <span className="font-data text-jarvis-faint">$</span>
                    <input
                      type="number"
                      step="0.01"
                      defaultValue={product.price ?? ""}
                      placeholder="—"
                      onBlur={(e) => saveField(product, "price", e.target.value)}
                      className={clsx(NUM_INPUT_CLASS, "w-20")}
                    />
                  </div>
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      step="0.1"
                      defaultValue={product.margin ?? ""}
                      placeholder="—"
                      onBlur={(e) => saveField(product, "margin", e.target.value)}
                      className={clsx(NUM_INPUT_CLASS, "w-16")}
                    />
                    <span className="font-data text-jarvis-faint">%</span>
                  </div>
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    defaultValue={product.inventory ?? ""}
                    placeholder="—"
                    onBlur={(e) => saveField(product, "inventory", e.target.value)}
                    className={clsx(NUM_INPUT_CLASS, "w-20")}
                  />
                </td>
                <td className="px-3 py-2">
                  <select
                    value={product.launch_status}
                    onChange={(e) => saveField(product, "launch_status", e.target.value)}
                    className={clsx(
                      "rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide transition-colors duration-150 focus:outline-none",
                      STATUS_STYLES[product.launch_status] ?? STATUS_STYLES.planning
                    )}
                  >
                    {LAUNCH_STATUSES.map((s) => (
                      <option key={s} value={s} className="bg-jarvis-panel text-jarvis-text">
                        {s.replace("_", " ")}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2 text-center">
                  {savingId === product.id && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-jarvis-muted" />
                  )}
                  {savedId === product.id && <Check className="h-3.5 w-3.5 text-jarvis-emerald" />}
                  {errorId === product.id && savingId !== product.id && savedId !== product.id && (
                    <span className="block h-1.5 w-1.5 rounded-full bg-jarvis-rose" />
                  )}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
