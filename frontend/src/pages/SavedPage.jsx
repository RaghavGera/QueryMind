import { useState } from "react";
import { AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Bookmark } from "lucide-react";
import { deleteSaved, getSaved } from "../services/savedApi";
import HistoryCard from "../components/history/HistoryCard";
import PageHeader from "../components/ui/PageHeader";

export default function SavedPage() {
  const [items, setItems] = useState(getSaved);
  const navigate = useNavigate();

  const handleReopen = (entry) => navigate(`/app?saved=${encodeURIComponent(entry.id)}`);
  const handleRerun = (entry) => navigate(`/app?q=${encodeURIComponent(entry.question)}`);
  const handleDelete = (id) => setItems(deleteSaved(id));

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 sm:px-6 py-10">
      <PageHeader label="Saved queries" title="Your pinned questions." detail="Pin questions you run often so they're one click away." />

      {items.length === 0 ? (
        <div className="hud flex flex-col items-center justify-center gap-2 py-16 text-center">
          <Bookmark size={22} className="text-ink-faint" />
          <p className="text-sm text-ink-dim">Nothing saved yet.</p>
          <p className="text-xs text-ink-faint">Run a query, then press Save above its result.</p>
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
              deleteLabel="Remove from saved"
            />
          ))}
        </AnimatePresence>
      )}
    </div>
  );
}
