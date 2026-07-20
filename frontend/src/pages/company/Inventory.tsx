import { Boxes } from "lucide-react";

import CompanyScopedPage from "@/components/CompanyScopedPage";
import DataTable, { type DataTableColumn } from "@/components/DataTable";
import ModulePageHeader from "@/components/ModulePageHeader";
import StatusPill from "@/components/StatusPill";
import { MOCK_INVENTORY } from "@/mock/inventory";
import type { InventoryItem } from "@/types";

const COLUMNS: DataTableColumn<InventoryItem>[] = [
  {
    key: "name",
    label: "Item",
    render: (i) => (
      <div>
        <p className="font-medium text-jarvis-text">{i.name}</p>
        <p className="text-xs text-jarvis-muted">{i.sku}</p>
      </div>
    ),
  },
  { key: "warehouse", label: "Location", render: (i) => i.warehouse ?? "—" },
  { key: "onHand", label: "On Hand", render: (i) => i.onHand.toLocaleString() },
  { key: "reserved", label: "Reserved", render: (i) => i.reserved.toLocaleString() },
  {
    key: "status",
    label: "Status",
    render: (i) =>
      i.onHand === 0 ? (
        <StatusPill label="Out of Stock" tone="danger" />
      ) : i.onHand <= i.reorderPoint ? (
        <StatusPill label="Reorder Soon" tone="progress" />
      ) : (
        <StatusPill label="In Stock" tone="success" />
      ),
  },
  {
    key: "value",
    label: "Value on Hand",
    render: (i) => (i.unitCost ? `$${(i.unitCost * i.onHand).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—"),
  },
];

export default function InventoryPage() {
  return (
    <CompanyScopedPage>
      {(company) => {
        const lowStock = MOCK_INVENTORY.filter((i) => i.onHand <= i.reorderPoint).length;
        return (
          <>
            <ModulePageHeader
              icon={Boxes}
              title="Inventory"
              description={`Stock levels across ${company.name}'s SKUs.`}
              actions={
                lowStock > 0 ? (
                  <StatusPill label={`${lowStock} need reordering`} tone="progress" />
                ) : (
                  <StatusPill label="All stocked" tone="success" />
                )
              }
            />
            <div className="hud-panel hud-corner min-h-0 flex-1 overflow-hidden">
              <DataTable columns={COLUMNS} rows={MOCK_INVENTORY} emptyLabel="No inventory tracked yet." />
            </div>
          </>
        );
      }}
    </CompanyScopedPage>
  );
}
