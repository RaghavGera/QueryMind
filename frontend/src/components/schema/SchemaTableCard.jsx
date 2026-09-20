import { motion } from "framer-motion";
import { KeyRound, Link2 } from "lucide-react";
import { cn } from "../../lib/utils";
import { formatNumber } from "../../lib/utils";

export default function SchemaTableCard({ table, active, onClick }) {
  return (
    <motion.button
      layout
      onClick={onClick}
      whileHover={{ y: -3 }}
      className={cn(
        "surface-card w-full max-w-xs shrink-0 p-0 text-left transition-shadow",
        active && "shadow-glow-sm border-accent-violet/50"
      )}
    >
      <div className="border-b border-line px-4 py-2.5">
        <div className="flex items-center justify-between">
          <span className="mono text-sm font-medium text-ink">{table.name}</span>
          <span className="text-xs text-ink-faint">{formatNumber(table.rowCount)} rows</span>
        </div>
      </div>
      <ul className="divide-y divide-line-soft">
        {table.columns.map((col) => (
          <li key={col.name} className="flex items-center justify-between px-4 py-1.5 text-xs">
            <span className="mono flex items-center gap-1.5 text-ink-dim">
              {col.pk && <KeyRound size={11} className="text-state-warning" />}
              {col.fk && <Link2 size={11} className="text-accent-glow" />}
              {col.name}
            </span>
            <span className="mono text-ink-faint">{col.type}</span>
          </li>
        ))}
      </ul>
    </motion.button>
  );
}
