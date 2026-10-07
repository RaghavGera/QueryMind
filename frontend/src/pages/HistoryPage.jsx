import { useEffect, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { History as HistoryIcon, Loader2 } from "lucide-react";
import { getHistory, deleteHistoryEntry } from "../services/historyApi";
import HistoryCard from "../components/history/HistoryCard";
import PageHeader from "../components/ui/PageHeader";

export default function HistoryPage() {
  const [items, setItems] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    getHistory().then(setItems);
  }, []);

  const handleDelete = async (id) => {
    setItems(await deleteHistoryEntry(id));
  };

  const handleReopen = (entry) => navigate(`/app?reopen=${encodeURIComponent(entry.id)}`);
  const handleRerun = (entry) => navigate(`/app?q=${encodeURIComponent(entry.question)}`);

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 sm:px-6 py-10">
      <PageHeader
        label="Query history"
        title="Everything you've asked."
        detail="Stored in this browser. Reopen shows the stored result; Re-run puts the question back in the Ask box."
      />

      {!items ? (
        <div className="flex h-40 items-center justify-center gap-2 text-ink-dim">
          <Loader2 size={16} className="animate-spin" /> Loading history...
        </div>
      ) : items.length === 0 ? (
        <div className="hud flex flex-col items-center justify-center gap-2 py-16 text-center">
          <HistoryIcon size={22} className="text-ink-faint" />
          <p className="text-sm text-ink-dim">No queries yet. Ask something to get started.</p>
        </div>
      ) : (
        <AnimatePresence>
          {items.map((entry) => (
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
