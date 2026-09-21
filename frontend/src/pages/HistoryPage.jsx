import { useEffect, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { History as HistoryIcon, Loader2 } from "lucide-react";
import { getHistory, deleteHistoryEntry } from "../services/historyApi";
import HistoryCard from "../components/history/HistoryCard";

export default function HistoryPage() {
  const [items, setItems] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    getHistory().then(setItems);
  }, []);

  const handleDelete = async (id) => {
    setItems(await deleteHistoryEntry(id));
  };

  const handleReopen = () => navigate("/app");
  const handleDuplicate = () => navigate("/app");

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 sm:px-6 py-10">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink">Query history</h1>
        <p className="mt-1 text-sm text-ink-dim">Every question you've asked, and how it resolved.</p>
      </div>

      {!items ? (
        <div className="flex h-40 items-center justify-center gap-2 text-ink-dim">
          <Loader2 size={16} className="animate-spin" /> Loading history...
        </div>
      ) : items.length === 0 ? (
        <div className="surface-card flex flex-col items-center justify-center gap-2 py-16 text-center">
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
              onDuplicate={handleDuplicate}
              onDelete={handleDelete}
            />
          ))}
        </AnimatePresence>
      )}
    </div>
  );
}
