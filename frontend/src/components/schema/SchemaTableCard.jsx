import { motion } from "framer-motion";
import { KeyRound, Link2 } from "lucide-react";
import { cn } from "../../lib/utils";

export default function SchemaTableCard({ table, active, onClick, index = 0 }) {
  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.25 }}
      onClick={onClick}
      whileHover={{ y: -3 }}
      aria-pressed={active}
      className={cn(
        "hud w-full p-0 text-left transition-shadow",
        active && "border-accent-cyan/40 shadow-[0_0_40px_-12px_rgba(94,234,212,0.6)]",
      )}
    >
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
        <span className="font-mono text-sm font-medium text-ink">{table.name}</span>
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-faint">{table.columns.length} cols</span>
      </div>
      <ul className="divide-y divide-white/[0.04]">
        {table.columns.map((col) => (
          <li key={col.name} className="flex items-center justify-between gap-3 px-4 py-1.5 text-xs">
            <span className="flex min-w-0 items-center gap-1.5 font-mono text-ink-dim">
              {col.pk && <KeyRound size={11} className="shrink-0 text-accent-amber" aria-label="primary key" />}
              {col.fk && <Link2 size={11} className="shrink-0 text-accent-cyan" aria-label={`references ${col.fk}`} />}
              <span className="truncate">{col.name}</span>
            </span>
            <span className="shrink-0 font-mono text-ink-faint">{col.type}</span>
          </li>
        ))}
      </ul>
    </motion.button>
  );
}
