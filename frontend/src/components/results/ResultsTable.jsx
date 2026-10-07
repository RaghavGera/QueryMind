import { useMemo, useState } from "react";
import { motion } from "framer-motion";
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
    // surface-card, not hud: overflow scrolling would clip the corner brackets.
    <div className="surface-card max-h-[28rem] overflow-auto" data-lenis-prevent>
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 z-10 bg-base-900/95 backdrop-blur">
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                onClick={() => toggleSort(col)}
                className="cursor-pointer select-none whitespace-nowrap border-b border-white/[0.08] px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink-dim transition-colors hover:text-accent-cyan"
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
            <motion.tr
              key={i}
              // The first rows fade in; long results appear instantly.
              initial={i < 20 ? { opacity: 0, x: -6 } : false}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.025, duration: 0.25 }}
              className={cn("transition-colors hover:bg-accent-violet/[0.06]", i % 2 === 1 && "bg-white/[0.015]")}
            >
              {columns.map((col) => (
                <td key={col} className="whitespace-nowrap border-b border-line-soft px-4 py-2.5 text-ink">
                  {typeof row[col] === "number" ? formatNumber(row[col]) : row[col]}
                </td>
              ))}
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
