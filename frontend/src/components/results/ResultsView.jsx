import { useEffect, useState } from "react";
import { animate, motion, useMotionValue } from "framer-motion";
import { Table2, LineChart as LineChartIcon, Inbox } from "lucide-react";
import { cn, formatDuration } from "../../lib/utils";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import CountUp from "../../motion/CountUp";
import ResultsTable from "./ResultsTable";
import ResultsChart from "./ResultsChart";

/** One row, one numeric column ("How many customers are there?"): show it big. */
function MetricCard({ label, value }) {
  const reduced = useReducedMotion();
  const progress = useMotionValue(reduced ? 1 : 0);
  useEffect(() => {
    if (reduced) return undefined;
    const controls = animate(progress, 1, { duration: 0.9, ease: "easeOut" });
    return () => controls.stop();
  }, [progress, reduced]);
  const decimals = Number.isInteger(value) ? 0 : 2;
  const format = (n) => n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

  return (
    <div className="hud flex flex-col items-start gap-2 px-6 py-6">
      <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">{label}</span>
      <CountUp
        progress={progress}
        to={value}
        format={format}
        className="font-display font-semibold tracking-tight text-gradient-neon [font-size:clamp(2.5rem,6vw,4.5rem)] leading-none"
      />
    </div>
  );
}

export default function ResultsView({ result, executionMs, dialect = "PostgreSQL" }) {
  const [view, setView] = useState("table");

  if (!result || result.rows.length === 0) {
    return (
      <div className="hud flex flex-col items-center justify-center gap-2 py-14 text-center">
        <Inbox size={22} className="text-ink-faint" />
        <p className="text-sm text-ink-dim">No rows matched this query.</p>
      </div>
    );
  }

  const { columns, rows } = result;
  const numericCols = columns.filter((c) => typeof rows[0][c] === "number");
  const nonNumericCols = columns.filter((c) => typeof rows[0][c] !== "number");
  const single = rows.length === 1 && columns.length === 1 && numericCols.length === 1;
  const canChart = !single && numericCols.length > 0 && nonNumericCols.length > 0 && columns.length <= 5;
  const xCandidate = nonNumericCols[0] ?? columns[0];
  const chartKind = /month|date|day|week|year|time/i.test(xCandidate) ? "line" : "bar";

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-ink-faint">
        <span>
          {[`${rows.length} row${rows.length === 1 ? "" : "s"}`, executionMs != null && `answered in ${formatDuration(executionMs)}`, dialect]
            .filter(Boolean)
            .join(" · ")}
        </span>
        {canChart && (
          <div className="flex overflow-hidden rounded-lg border border-white/[0.08] normal-case tracking-normal">
            <button
              onClick={() => setView("table")}
              className={cn("flex items-center gap-1.5 px-3 py-1.5 text-xs", view === "table" ? "bg-white/[0.08] text-ink" : "text-ink-dim")}
            >
              <Table2 size={13} /> Table
            </button>
            <button
              onClick={() => setView("chart")}
              className={cn("flex items-center gap-1.5 px-3 py-1.5 text-xs", view === "chart" ? "bg-white/[0.08] text-ink" : "text-ink-dim")}
            >
              <LineChartIcon size={13} /> Chart
            </button>
          </div>
        )}
      </div>

      {single ? (
        <MetricCard label={columns[0]} value={rows[0][columns[0]]} />
      ) : view === "table" || !canChart ? (
        <ResultsTable columns={columns} rows={rows} />
      ) : (
        <ResultsChart columns={columns} rows={rows} kind={chartKind} />
      )}
    </motion.div>
  );
}
