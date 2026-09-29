import type { ReactNode } from "react";

interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  width?: string;
  align?: "left" | "right" | "center";
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  onRowClick?: (row: T) => void;
  loading?: boolean;
  emptyMessage?: string;
}

export default function Table<T extends { id: string }>({
  columns,
  rows,
  onRowClick,
  loading,
  emptyMessage = "No records found.",
}: Props<T>) {
  return (
    <div className="border border-[#E2E8F0] rounded-lg overflow-hidden bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-[#F8F9FB] border-b border-[#E2E8F0]">
            {columns.map((col) => (
              <th
                key={col.key}
                style={{ width: col.width }}
                className={`px-4 py-3 text-xs font-semibold text-[#64748B] tracking-wide uppercase text-${col.align ?? "left"}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-12 text-center text-[#94A3B8] text-sm">
                <div className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="#CBD5E1" strokeWidth="2.5" />
                    <path d="M12 2a10 10 0 0 1 10 10" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round" />
                  </svg>
                  Loading…
                </div>
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-12 text-center text-[#94A3B8] text-sm">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr
                key={row.id}
                onClick={() => onRowClick?.(row)}
                className={`border-b border-[#F1F5F9] last:border-0 transition-colors ${
                  onRowClick ? "cursor-pointer hover:bg-[#F8F9FB]" : ""
                } ${i % 2 === 0 ? "" : "bg-[#FAFBFC]"}`}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-4 py-3 text-[#0F172A] text-${col.align ?? "left"}`}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
