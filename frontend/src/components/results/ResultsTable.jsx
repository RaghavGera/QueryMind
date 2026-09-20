import { useMemo, useState } from "react";
import { ArrowUp, ArrowDown } from "lucide-react";
import { cn, formatNumber } from "../../lib/utils";

export default function ResultsTable({ columns, rows }) {
  const [sort, setSort] = useState({ key: null, dir: "asc" });

  const sorted = useMemo(() => {
    if (!sort.key) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (typeof av === "number" && typeof bv === "number") {
        return sort.dir === "asc" ? av - bv : bv - av;
      }
      return sort.dir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return copy;
  }, [rows, sort]);

  const toggleSort = (key) => {
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
  };

  return (
    <div className="overflow-auto rounded-xl border border-line">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-base-900/95 backdrop-blur">
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                onClick={() => toggleSort(col)}
                className="cursor-pointer select-none whitespace-nowrap border-b border-line px-4 py-2.5 font-medium text-ink-dim transition-colors hover:text-ink"
              >
                <span className="inline-flex items-center gap-1">
                  {col}
                  {sort.key === col && (sort.dir === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i} className={cn("transition-colors hover:bg-white/[0.03]", i % 2 === 1 && "bg-white/[0.015]")}>
              {columns.map((col) => (
                <td key={col} className="whitespace-nowrap border-b border-line-soft px-4 py-2.5 text-ink">
                  {typeof row[col] === "number" ? formatNumber(row[col]) : row[col]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
