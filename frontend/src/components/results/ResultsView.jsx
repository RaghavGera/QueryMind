import { useState } from "react";
import { motion } from "framer-motion";
import { Table2, LineChart as LineChartIcon, Inbox } from "lucide-react";
import { cn } from "../../lib/utils";
import ResultsTable from "./ResultsTable";
import ResultsChart from "./ResultsChart";

export default function ResultsView({ result, executionMs, dialect = "PostgreSQL" }) {
  const [view, setView] = useState("table");

  if (!result || result.rows.length === 0) {
    return (
      <div className="surface-card flex flex-col items-center justify-center gap-2 py-14 text-center">
        <Inbox size={22} className="text-ink-faint" />
        <p className="text-sm text-ink-dim">No rows matched this query.</p>
      </div>
    );
  }

  const { columns, rows } = result;
  const numericCols = columns.filter((c) => typeof rows[0][c] === "number");
  const nonNumericCols = columns.filter((c) => typeof rows[0][c] !== "number");
  const canChart = numericCols.length > 0 && nonNumericCols.length > 0 && columns.length <= 5;
  const xCandidate = nonNumericCols[0] ?? columns[0];
  const chartKind = /month|date|day|week|year|time/i.test(xCandidate) ? "line" : "bar";

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-dim">
        <span>
          {rows.length} rows · Executed in {executionMs}ms · {dialect}
        </span>
        {canChart && (
          <div className="flex overflow-hidden rounded-lg border border-line">
            <button
              onClick={() => setView("table")}
              className={cn("flex items-center gap-1.5 px-3 py-1.5", view === "table" ? "bg-white/[0.08] text-ink" : "text-ink-dim")}
            >
              <Table2 size={13} /> Table
            </button>
            <button
              onClick={() => setView("chart")}
              className={cn("flex items-center gap-1.5 px-3 py-1.5", view === "chart" ? "bg-white/[0.08] text-ink" : "text-ink-dim")}
            >
              <LineChartIcon size={13} /> Chart
            </button>
          </div>
        )}
      </div>

      {view === "table" || !canChart ? (
        <ResultsTable columns={columns} rows={rows} />
      ) : (
        <ResultsChart columns={columns} rows={rows} kind={chartKind} />
      )}
    </motion.div>
  );
}
