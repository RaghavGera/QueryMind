import { motion } from "framer-motion";
import { RotateCcw, Copy, Trash2 } from "lucide-react";
import { Badge } from "../ui/Surfaces";
import { relativeTime } from "../../lib/utils";

const statusTone = { success: "success", clarification: "warning", failed: "danger" };
const statusLabel = { success: "Successful", clarification: "Clarification required", failed: "Failed" };

export default function HistoryCard({ entry, onReopen, onDuplicate, onDelete }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0 }}
      className="surface-card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-ink">{entry.question}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-dim">
          <Badge tone={statusTone[entry.status]}>{statusLabel[entry.status]}</Badge>
          {entry.resolved && <span>Resolved: {entry.resolved}</span>}
          <span>{relativeTime(entry.executedAt)}</span>
          {entry.durationMs && <span>{entry.durationMs}ms</span>}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button onClick={() => onReopen(entry)} className="btn-ghost" title="Reopen">
          <RotateCcw size={14} />
        </button>
        <button onClick={() => onDuplicate(entry)} className="btn-ghost" title="Duplicate">
          <Copy size={14} />
        </button>
        <button onClick={() => onDelete(entry.id)} className="btn-ghost hover:!text-state-danger" title="Delete">
          <Trash2 size={14} />
        </button>
      </div>
    </motion.div>
  );
}
