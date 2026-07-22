import { useCallback, useEffect, useState } from "react";
import { Check, ImageOff, Loader2, PackageX } from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import { useToast } from "@/context/ToastContext";
import type { BrandProduct, Product } from "@/types";

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

/** One row: a real store product, plus the launch-prep record kept alongside it. */
interface LaunchRow {
  /** The live Shopify product — null only for a workspace with no store. */
  store: BrandProduct | null;
  /** Jarvis's own launch-tracking record, once one exists for this product. */
  ops: Product | null;
  key: string;
  title: string;
}

/** Shopify identity matched to an ops record by title, then by handle. */
function linkOps(store: BrandProduct, ops: Product[]): Product | null {
  const title = store.title.trim().toLowerCase();
  const handle = (store.handle ?? "").trim().toLowerCase();
  return (
    ops.find((p) => p.name.trim().toLowerCase() === title) ??
    ops.find((p) => handle && p.name.trim().toLowerCase() === handle) ??
    null
  );
}

function money(value: number | null, currency: string | null): string {
  if (value === null || value === undefined) return "—";
  return `${currency === "USD" || !currency ? "$" : ""}${value.toFixed(2)}`;
}

/**
 * LAUNCH DASHBOARD — the five real products, not a list someone typed in.
 *
 * Identity, image, price, inventory, and storefront status come from the Brand
 * Brain (the synced Shopify catalog, the workspace's source of truth) and are
 * shown READ-ONLY: Shopify owns those facts, and changing them is an
 * approval-gated operation, not an inline edit that would silently disagree
 * with the store.
 *
 * The launch-prep columns beside them — manufacturer, packaging, MOQ, COGS,
 * freight, margin, launch status — are Jarvis's own operational record, which
 * Shopify has no concept of, so those stay editable and save exactly as before.
 * The two are joined per product; a store product with no launch record yet
 * gets one created the first time you type in it.
 *
 * A workspace with no synced store falls back to the plain product list, so
 * non-commerce workspaces keep working unchanged.
 */
export default function LaunchDashboard({
  companyId,
  products,
  onChange,
}: {
  companyId: string;
  products: Product[];
  onChange: (products: Product[]) => void;
}) {
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [storeProducts, setStoreProducts] = useState<BrandProduct[] | null>(null);
  const [loadingStore, setLoadingStore] = useState(true);
  const toast = useToast();

  useEffect(() => {
    let cancelled = false;
    setLoadingStore(true);
    api
      .listBrandProducts(companyId)
      .then((list) => !cancelled && setStoreProducts(list))
      .catch(() => !cancelled && setStoreProducts([]))
      .finally(() => !cancelled && setLoadingStore(false));
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  const hasStore = (storeProducts?.length ?? 0) > 0;
  const rows: LaunchRow[] = hasStore
    ? storeProducts!.map((store) => ({
        store,
        ops: linkOps(store, products),
        key: store.id,
        title: store.title,
      }))
    : products.map((p) => ({ store: null, ops: p, key: p.id, title: p.name }));

  // Launch records that don't correspond to anything in the store. Disclosed
  // rather than hidden — but they aren't shown as if they were real products.
  const unmatched = hasStore
    ? products.filter((p) => !storeProducts!.some((s) => linkOps(s, [p])))
    : [];

  const saveField = useCallback(
    async (row: LaunchRow, field: keyof Product, value: string) => {
      let parsed: string | number | null = value;
      if (["cogs", "freight", "price", "margin"].includes(field as string)) {
        parsed = value === "" ? null : Number(value);
      } else if (["moq", "inventory"].includes(field as string)) {
        parsed = value === "" ? null : parseInt(value, 10);
      } else if (value === "") {
        parsed = null;
      }

      setSavingKey(row.key);
      setErrorKey(null);
      try {
        // First edit on a store product that has no launch record yet: create
        // it under the real product's name so the two stay linked.
        let ops = row.ops;
        if (!ops) {
          ops = await api.createProduct(companyId, row.title);
          onChange([...products, ops]);
        }
        const updated = await api.updateProduct(companyId, ops.id, { [field]: parsed });
        onChange(
          products.some((p) => p.id === updated.id)
            ? products.map((p) => (p.id === updated.id ? updated : p))
            : [...products, updated]
        );
        setSavedKey(row.key);
        setTimeout(() => setSavedKey((cur) => (cur === row.key ? null : cur)), 1200);
      } catch (err) {
        setErrorKey(row.key);
        toast.push(
          err instanceof ApiError ? `Failed to save: ${err.message}` : "Failed to save change.",
          "error"
        );
      } finally {
        setSavingKey(null);
      }
    },
    [companyId, onChange, products, toast]
  );

  return (
    <div className="flex flex-col lg:h-full lg:overflow-hidden">
      <div className="flex items-center justify-between px-1 pb-3">
        <div>
          <h3 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
            LAUNCH DASHBOARD
          </h3>
          <p className="text-xs text-jarvis-muted">
            {hasStore
              ? "Your live Shopify products. Price, stock, and status are read from the store; launch-prep fields are yours to fill in."
              : "Launch tracking — fields start empty and are saved as they're entered."}
          </p>
        </div>
      </div>

      {loadingStore && !storeProducts ? (
        <div className="space-y-2 rounded-xl border border-jarvis-border/60 p-4">
          <div className="skeleton h-4 w-1/3 rounded" />
          <div className="skeleton h-3 w-full rounded" />
        </div>
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-jarvis-border/60 p-6 text-center text-sm text-jarvis-muted">
          No products in this workspace yet.
        </p>
      ) : (
        <div className="hidden flex-1 overflow-auto rounded-xl border border-jarvis-border/60 lg:block">
          <table className="w-full min-w-[1180px] border-collapse text-sm">
            <thead className="sticky top-0 z-10 bg-jarvis-panel2/95 shadow-[0_1px_0_0_theme(colors.jarvis.border)] backdrop-blur-xl">
              <tr className="text-left text-[11px] uppercase tracking-wide text-jarvis-muted">
                <th className="px-3 py-2.5 font-medium">Product</th>
                {hasStore && <th className="px-3 py-2.5 font-medium">Store price</th>}
                {hasStore && <th className="px-3 py-2.5 font-medium">Store stock</th>}
                {hasStore && <th className="px-3 py-2.5 font-medium">Storefront</th>}
                <th className="px-3 py-2.5 font-medium">Manufacturer</th>
                <th className="px-3 py-2.5 font-medium">Packaging</th>
                <th className="px-3 py-2.5 font-medium">MOQ</th>
                <th className="px-3 py-2.5 font-medium">COGS</th>
                <th className="px-3 py-2.5 font-medium">Freight</th>
                {!hasStore && <th className="px-3 py-2.5 font-medium">Price</th>}
                <th className="px-3 py-2.5 font-medium">Margin %</th>
                {!hasStore && <th className="px-3 py-2.5 font-medium">Inventory</th>}
                <th className="px-3 py-2.5 font-medium">Launch Status</th>
                <th className="w-8 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                const { store, ops } = row;
                const outOfStock = store?.total_inventory !== null && store?.total_inventory === 0;
                return (
                  <motion.tr
                    key={row.key}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.03 * i, duration: 0.25 }}
                    className="border-t border-jarvis-border/40 transition-colors duration-150 hover:bg-jarvis-panel2/30"
                  >
                    {/* Identity comes from the store — not editable here. */}
                    <td className="px-3 py-2">
                      {store ? (
                        <div className="flex items-center gap-2.5">
                          {store.featured_image ? (
                            <img
                              src={store.featured_image}
                              alt=""
                              loading="lazy"
                              className="h-10 w-10 shrink-0 rounded-lg border border-jarvis-border/50 object-cover"
                            />
                          ) : (
                            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-jarvis-border/50 bg-jarvis-panel2/40">
                              <ImageOff className="h-4 w-4 text-jarvis-faint" />
                            </span>
                          )}
                          <div className="min-w-0">
                            <p className="truncate font-medium text-jarvis-text">{store.title}</p>
                            <p className="truncate font-data text-[10px] text-jarvis-faint">
                              {store.handle ?? "—"}
                            </p>
                          </div>
                        </div>
                      ) : (
                        <input
                          defaultValue={ops?.name ?? ""}
                          onBlur={(e) => saveField(row, "name", e.target.value)}
                          className={clsx(INPUT_CLASS, "w-32")}
                        />
                      )}
                    </td>

                    {hasStore && (
                      <td className="px-3 py-2 font-data text-jarvis-text">
                        {store
                          ? store.price_min !== null && store.price_max !== null && store.price_min !== store.price_max
                            ? `${money(store.price_min, store.currency)}–${money(store.price_max, store.currency)}`
                            : money(store.price_min, store.currency)
                          : "—"}
                      </td>
                    )}
                    {hasStore && (
                      <td className="px-3 py-2">
                        {store?.total_inventory === null || store?.total_inventory === undefined ? (
                          <span className="text-jarvis-faint">Unknown</span>
                        ) : (
                          <span
                            className={clsx(
                              "font-data",
                              outOfStock ? "font-semibold text-jarvis-rose" : "text-jarvis-text"
                            )}
                          >
                            {store.total_inventory}
                            {outOfStock && (
                              <span className="ml-1.5 inline-flex items-center gap-1 rounded bg-jarvis-rose/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wide">
                                <PackageX className="h-3 w-3" /> out
                              </span>
                            )}
                          </span>
                        )}
                      </td>
                    )}
                    {hasStore && (
                      <td className="px-3 py-2">
                        <span
                          className={clsx(
                            "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                            store?.status === "ACTIVE"
                              ? "border-jarvis-emerald/40 bg-jarvis-emerald/10 text-jarvis-emerald"
                              : "border-jarvis-muted/40 bg-jarvis-muted/10 text-jarvis-muted"
                          )}
                        >
                          {store?.status?.toLowerCase() ?? "unknown"}
                        </span>
                      </td>
                    )}

                    {/* Launch prep — Jarvis's own record, editable. */}
                    <td className="px-3 py-2">
                      <input
                        defaultValue={ops?.manufacturer ?? ""}
                        placeholder="TBD"
                        onBlur={(e) => saveField(row, "manufacturer", e.target.value)}
                        className={clsx(INPUT_CLASS, "w-32")}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        defaultValue={ops?.packaging ?? ""}
                        placeholder="TBD"
                        onBlur={(e) => saveField(row, "packaging", e.target.value)}
                        className={clsx(INPUT_CLASS, "w-28")}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        defaultValue={ops?.moq ?? ""}
                        placeholder="—"
                        onBlur={(e) => saveField(row, "moq", e.target.value)}
                        className={clsx(NUM_INPUT_CLASS, "w-20")}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <span className="font-data text-jarvis-faint">$</span>
                        <input
                          type="number"
                          step="0.01"
                          defaultValue={ops?.cogs ?? ""}
                          placeholder="—"
                          onBlur={(e) => saveField(row, "cogs", e.target.value)}
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
                          defaultValue={ops?.freight ?? ""}
                          placeholder="—"
                          onBlur={(e) => saveField(row, "freight", e.target.value)}
                          className={clsx(NUM_INPUT_CLASS, "w-20")}
                        />
                      </div>
                    </td>
                    {!hasStore && (
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1">
                          <span className="font-data text-jarvis-faint">$</span>
                          <input
                            type="number"
                            step="0.01"
                            defaultValue={ops?.price ?? ""}
                            placeholder="—"
                            onBlur={(e) => saveField(row, "price", e.target.value)}
                            className={clsx(NUM_INPUT_CLASS, "w-20")}
                          />
                        </div>
                      </td>
                    )}
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          step="0.1"
                          defaultValue={ops?.margin ?? ""}
                          placeholder="—"
                          onBlur={(e) => saveField(row, "margin", e.target.value)}
                          className={clsx(NUM_INPUT_CLASS, "w-16")}
                        />
                        <span className="font-data text-jarvis-faint">%</span>
                      </div>
                    </td>
                    {!hasStore && (
                      <td className="px-3 py-2">
                        <input
                          type="number"
                          defaultValue={ops?.inventory ?? ""}
                          placeholder="—"
                          onBlur={(e) => saveField(row, "inventory", e.target.value)}
                          className={clsx(NUM_INPUT_CLASS, "w-20")}
                        />
                      </td>
                    )}
                    <td className="px-3 py-2">
                      <select
                        value={ops?.launch_status ?? (store?.status === "ACTIVE" ? "launched" : "planning")}
                        onChange={(e) => saveField(row, "launch_status", e.target.value)}
                        className={clsx(
                          "rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide transition-colors duration-150 focus:outline-none",
                          STATUS_STYLES[
                            ops?.launch_status ?? (store?.status === "ACTIVE" ? "launched" : "planning")
                          ] ?? STATUS_STYLES.planning
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
                      {savingKey === row.key && (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-jarvis-muted" />
                      )}
                      {savedKey === row.key && <Check className="h-3.5 w-3.5 text-jarvis-emerald" />}
                      {errorKey === row.key && savingKey !== row.key && savedKey !== row.key && (
                        <span className="block h-1.5 w-1.5 rounded-full bg-jarvis-rose" />
                      )}
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Phone layout: one card per product. A 1180px table can't be operated
          with a thumb, and this is the surface the workshop is run from. */}
      {rows.length > 0 && (
        <div className="space-y-2 lg:hidden">
          {rows.map((row) => (
            <LaunchCard
              key={row.key}
              row={row}
              hasStore={hasStore}
              busy={savingKey === row.key}
              saved={savedKey === row.key}
              failed={errorKey === row.key}
              onSave={saveField}
            />
          ))}
        </div>
      )}

      {hasStore && (
        <p className="px-1 pt-2 text-[11px] text-jarvis-muted">
          {rows.length} product{rows.length === 1 ? "" : "s"} from your live Shopify catalog. Price, stock,
          and storefront status are read from the store — changing them goes through an approval.
          {unmatched.length > 0 &&
            ` ${unmatched.length} launch record${unmatched.length === 1 ? "" : "s"} (${unmatched
              .map((p) => p.name)
              .join(", ")}) don't match anything in the store and aren't shown as products.`}
        </p>
      )}
    </div>
  );
}


/** One product on a phone: the store's facts up top, launch prep below. */
function LaunchCard({
  row,
  hasStore,
  busy,
  saved,
  failed,
  onSave,
}: {
  row: LaunchRow;
  hasStore: boolean;
  busy: boolean;
  saved: boolean;
  failed: boolean;
  onSave: (row: LaunchRow, field: keyof Product, value: string) => void;
}) {
  const { store, ops } = row;
  const outOfStock = store?.total_inventory === 0;
  const status = ops?.launch_status ?? (store?.status === "ACTIVE" ? "launched" : "planning");

  return (
    <article className="rounded-xl border border-jarvis-border/50 bg-jarvis-panel2/20 p-3">
      <div className="flex items-start gap-3">
        {store?.featured_image ? (
          <img
            src={store.featured_image}
            alt=""
            loading="lazy"
            className="h-14 w-14 shrink-0 rounded-lg border border-jarvis-border/50 object-cover"
          />
        ) : (
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border border-jarvis-border/50 bg-jarvis-panel2/40">
            <ImageOff className="h-4 w-4 text-jarvis-faint" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-snug text-jarvis-text">{row.title}</p>
          {hasStore && store && (
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
              <span className="font-data text-jarvis-text">
                {store.price_min !== null && store.price_max !== null && store.price_min !== store.price_max
                  ? `${money(store.price_min, store.currency)}–${money(store.price_max, store.currency)}`
                  : money(store.price_min, store.currency)}
              </span>
              <span
                className={clsx(
                  "font-data",
                  outOfStock ? "font-semibold text-jarvis-rose" : "text-jarvis-muted"
                )}
              >
                {store.total_inventory === null || store.total_inventory === undefined
                  ? "stock unknown"
                  : `${store.total_inventory} in stock`}
              </span>
              <span
                className={clsx(
                  "rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                  store.status === "ACTIVE"
                    ? "border-jarvis-emerald/40 bg-jarvis-emerald/10 text-jarvis-emerald"
                    : "border-jarvis-muted/40 bg-jarvis-muted/10 text-jarvis-muted"
                )}
              >
                {store.status?.toLowerCase() ?? "unknown"}
              </span>
            </div>
          )}
        </div>
        <span className="w-4 shrink-0 pt-1">
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-jarvis-muted" />}
          {saved && !busy && <Check className="h-3.5 w-3.5 text-jarvis-emerald" />}
          {failed && !busy && !saved && <span className="block h-1.5 w-1.5 rounded-full bg-jarvis-rose" />}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-jarvis-border/40 pt-2">
        <Field label="Manufacturer" value={ops?.manufacturer ?? ""} onSave={(v) => onSave(row, "manufacturer", v)} />
        <Field label="Packaging" value={ops?.packaging ?? ""} onSave={(v) => onSave(row, "packaging", v)} />
        <Field label="MOQ" value={ops?.moq ?? ""} numeric onSave={(v) => onSave(row, "moq", v)} />
        <Field label="COGS" value={ops?.cogs ?? ""} numeric prefix="$" onSave={(v) => onSave(row, "cogs", v)} />
        <Field label="Freight" value={ops?.freight ?? ""} numeric prefix="$" onSave={(v) => onSave(row, "freight", v)} />
        <Field label="Margin %" value={ops?.margin ?? ""} numeric onSave={(v) => onSave(row, "margin", v)} />
      </div>

      <label className="mt-2 flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-wide text-jarvis-faint">Launch</span>
        <select
          value={status}
          onChange={(e) => onSave(row, "launch_status", e.target.value)}
          className={clsx(
            "rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide focus:outline-none",
            STATUS_STYLES[status] ?? STATUS_STYLES.planning
          )}
        >
          {LAUNCH_STATUSES.map((s) => (
            <option key={s} value={s} className="bg-jarvis-panel text-jarvis-text">
              {s.replace("_", " ")}
            </option>
          ))}
        </select>
      </label>
    </article>
  );
}

function Field({
  label,
  value,
  numeric,
  prefix,
  onSave,
}: {
  label: string;
  value: string | number;
  numeric?: boolean;
  prefix?: string;
  onSave: (value: string) => void;
}) {
  return (
    <label className="min-w-0">
      <span className="block text-[10px] uppercase tracking-wide text-jarvis-faint">{label}</span>
      <span className="flex items-center gap-1">
        {prefix && <span className="font-data text-xs text-jarvis-faint">{prefix}</span>}
        <input
          type={numeric ? "number" : "text"}
          step={numeric ? "0.01" : undefined}
          defaultValue={value}
          placeholder="—"
          onBlur={(e) => onSave(e.target.value)}
          className={clsx(
            "w-full min-w-0 rounded-lg border border-jarvis-border/60 bg-jarvis-panel2/40 px-2 py-1.5 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none",
            numeric && "font-data"
          )}
        />
      </span>
    </label>
  );
}
