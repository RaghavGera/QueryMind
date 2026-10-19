import { useState } from "react";
import { AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Bookmark, Loader2 } from "lucide-react";
import { library, useLibrary } from "../hooks/useLibrary";
import { useAuth } from "../auth/AuthProvider";
import HistoryCard from "../components/history/HistoryCard";
import PageHeader from "../components/ui/PageHeader";

export default function SavedPage() {
  const { status, saved, error } = useLibrary();
  const signedIn = useAuth().status === "signedIn";
  const [problem, setProblem] = useState(null);
  const navigate = useNavigate();

  const handleReopen = (entry) => navigate(`/app?saved=${encodeURIComponent(entry.id)}`);
  const handleRerun = (entry) => navigate(`/app?q=${encodeURIComponent(entry.question)}`);
  const handleDelete = (id) => {
    setProblem(null);
    library.removeSaved(id).catch((e) => setProblem(e.message));
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 sm:px-6 py-10">
      <PageHeader
        label="Saved queries"
        title="Your pinned questions."
        detail={
          signedIn
            ? "Pin questions you run often so they're one click away. Saved in your account."
            : "Pin questions you run often so they're one click away. Saved in this browser until you sign in."
        }
      />

      {(problem || status === "error") && (
        <p className="flex items-start gap-2 text-sm text-state-danger">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          {problem || error}
        </p>
      )}

      {status === "loading" || status === "idle" ? (
        <div className="flex h-40 items-center justify-center gap-2 text-ink-dim">
          <Loader2 size={16} className="animate-spin" /> Loading saved queries...
        </div>
      ) : saved.length === 0 ? (
        status === "ready" && (
          <div className="hud flex flex-col items-center justify-center gap-2 py-16 text-center">
            <Bookmark size={22} className="text-ink-faint" />
            <p className="text-sm text-ink-dim">Nothing saved yet.</p>
            <p className="text-xs text-ink-faint">Run a query, then press Save above its result.</p>
          </div>
        )
      ) : (
        <AnimatePresence>
          {saved.map((entry) => (
            <HistoryCard
              key={entry.id}
              entry={entry}
              onReopen={handleReopen}
              onRerun={handleRerun}
              onDelete={handleDelete}
              deleteLabel="Remove from saved"
            />
          ))}
        </AnimatePresence>
      )}
    </div>
  );
}
