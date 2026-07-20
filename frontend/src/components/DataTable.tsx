import type { ReactNode } from "react";

export interface DataTableColumn<T> {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  className?: string;
}

/**
 * Small generic table shared by every list-style module (CRM, Inventory,
 * SOP Library, Amazon Launch Center, ...). Columns declare how to render
 * each cell, so each module stays in control of its own data shape.
 */
export default function DataTable<T extends { id: string }>({
  columns,
  rows,
  emptyLabel = "Nothing here yet.",
}: {
  columns: DataTableColumn<T>[];
  rows: T[];
  emptyLabel?: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center py-16 text-sm text-jarvis-muted">
        {emptyLabel}
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-jarvis-border/60 text-xs uppercase tracking-wide text-jarvis-muted">
            {columns.map((col) => (
              <th key={col.key} className={`px-3 py-2.5 font-medium ${col.className ?? ""}`}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className="border-b border-jarvis-border/30 text-jarvis-text transition-colors duration-150 hover:bg-jarvis-panel2/40"
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-3 py-2.5 ${col.className ?? ""}`}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
