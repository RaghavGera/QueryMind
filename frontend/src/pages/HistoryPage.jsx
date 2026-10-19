import { useState } from "react";
import { AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, History as HistoryIcon, Loader2 } from "lucide-react";
import { library, useLibrary } from "../hooks/useLibrary";
import { useAuth } from "../auth/AuthProvider";
import HistoryCard from "../components/history/HistoryCard";
import PageHeader from "../components/ui/PageHeader";

export default function HistoryPage() {
  const { status, history, error } = useLibrary();
  const signedIn = useAuth().status === "signedIn";
  const [problem, setProblem] = useState(null);
  const navigate = useNavigate();

  const handleDelete = (id) => {
    setProblem(null);
    library.removeHistory(id).catch((e) => setProblem(e.message));
  };

  const handleReopen = (entry) => navigate(`/app?reopen=${encodeURIComponent(entry.id)}`);
  const handleRerun = (entry) => navigate(`/app?q=${encodeURIComponent(entry.question)}`);

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 sm:px-6 py-10">
      <PageHeader
        label="Query history"
        title="Everything you've asked."
        detail={`${
          signedIn ? "Stored in your account, on every device you sign in on." : "Stored in this browser until you sign in."
        } Reopen shows the stored result; Re-run puts the question back in the Ask box.`}
      />

      {(problem || status === "error") && (
        <p className="flex items-start gap-2 text-sm text-state-danger">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          {problem || error}
        </p>
      )}

      {status === "loading" || status === "idle" ? (
        <div className="flex h-40 items-center justify-center gap-2 text-ink-dim">
          <Loader2 size={16} className="animate-spin" /> Loading history...
        </div>
      ) : history.length === 0 ? (
        status === "ready" && (
          <div className="hud flex flex-col items-center justify-center gap-2 py-16 text-center">
            <HistoryIcon size={22} className="text-ink-faint" />
            <p className="text-sm text-ink-dim">No queries yet. Ask something to get started.</p>
          </div>
        )
      ) : (
        <AnimatePresence>
          {history.map((entry) => (
            <HistoryCard
              key={entry.id}
              entry={entry}
              onReopen={handleReopen}
              onRerun={handleRerun}
              onDelete={handleDelete}
            />
          ))}
        </AnimatePresence>
      )}
    </div>
  );
}
