import { AnimatePresence } from "framer-motion";
import { useWorkspaces, workspaces } from "../../hooks/useWorkspaces";
import { splitByWorkspace } from "../../services/workspaces.js";
import HistoryCard from "./HistoryCard";

/**
 * History or saved entries of the active workspace, then those of workspaces
 * that expired (their stored results still reopen). ``empty`` shows when the
 * active workspace has none.
 */
export default function EntryList({ entries, empty, onReopen, onRerun, onDelete, deleteLabel }) {
  const { status, activeId } = useWorkspaces();
  // Until the list has loaded, nothing counts as expired.
  const known = (id) => status !== "ready" || workspaces.isKnown(id);
  const { current, expired, elsewhere } = splitByWorkspace(entries, activeId, known);
  const card = (entry, tag) => (
    <HistoryCard key={entry.id} entry={entry} onReopen={onReopen} onRerun={onRerun} onDelete={onDelete} deleteLabel={deleteLabel} tag={tag} />
  );

  return (
    <div className="space-y-4">
      {current.length === 0 ? empty : <AnimatePresence>{current.map((entry) => card(entry))}</AnimatePresence>}
      {elsewhere > 0 && (
        <p className="text-xs text-ink-faint">
          {elsewhere} more in your other workspace. Switch workspace in the top bar to see {elsewhere === 1 ? "it" : "them"}.
        </p>
      )}
      {expired.length > 0 && (
        <section className="space-y-3 pt-4">
          <p className="hud-label">From expired workspaces</p>
          <p className="text-xs text-ink-faint">Their data is gone, but Reopen still shows the stored result.</p>
          <AnimatePresence>{expired.map((entry) => card(entry, "Workspace expired"))}</AnimatePresence>
        </section>
      )}
    </div>
  );
}
