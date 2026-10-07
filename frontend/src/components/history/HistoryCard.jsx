import { motion } from "framer-motion";
import { FolderOpen, RefreshCcw, Trash2 } from "lucide-react";
import { Badge } from "../ui/Surfaces";
import { formatDuration, relativeTime } from "../../lib/utils";

const statusTone = { success: "success", clarification: "warning", failed: "danger" };
const statusLabel = { success: "Successful", clarification: "Clarification required", failed: "Failed" };

/*
 * One stored query, used by Query History and Saved Queries.
 *   Reopen  shows the stored result without calling the backend
 *   Re-run  puts the question in the Ask box (the user submits it)
 */
export default function HistoryCard({ entry, onReopen, onRerun, onDelete, deleteLabel = "Delete" }) {
  const snapshot = entry.snapshot;
  const when = entry.savedAt || entry.executedAt;
  const rowCount = snapshot ? snapshot.totalRows ?? snapshot.rows.length : 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0 }}
      className="hud flex flex-col gap-3 p-4 transition-shadow duration-300 hover:shadow-[0_0_40px_-16px_rgba(94,234,212,0.55)] sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-ink">{entry.question}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-dim">
          {entry.status && <Badge tone={statusTone[entry.status]}>{statusLabel[entry.status]}</Badge>}
          {entry.resolved && <span>Clarified: {entry.resolved}</span>}
          {snapshot && <span>{rowCount} row{rowCount === 1 ? "" : "s"}</span>}
          {when && <span>{entry.savedAt ? "Saved " : ""}{relativeTime(when)}</span>}
          {entry.durationMs != null && <span>{formatDuration(entry.durationMs)}</span>}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button
          onClick={() => onReopen(entry)}
          disabled={!snapshot}
          className="btn-ghost disabled:cursor-not-allowed disabled:opacity-40"
          title={snapshot ? "Reopen" : "Nothing to reopen (no stored result)"}
          aria-label="Reopen"
        >
          <FolderOpen size={14} />
        </button>
        <button onClick={() => onRerun(entry)} className="btn-ghost" title="Re-run" aria-label="Re-run">
          <RefreshCcw size={14} />
        </button>
        <button
          onClick={() => onDelete(entry.id)}
          className="btn-ghost hover:!text-state-danger"
          title={deleteLabel}
          aria-label={deleteLabel}
        >
          <Trash2 size={14} />
        </button>
      </div>
    </motion.div>
  );
}
