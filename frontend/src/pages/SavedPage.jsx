import { Bookmark } from "lucide-react";

export default function SavedPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
      <h1 className="font-display text-2xl font-semibold text-ink">Saved queries</h1>
      <p className="mt-1 text-sm text-ink-dim">Pin questions you run often so they're one click away.</p>

      <div className="surface-card mt-6 flex flex-col items-center justify-center gap-2 py-16 text-center">
        <Bookmark size={22} className="text-ink-faint" />
        <p className="text-sm text-ink-dim">Nothing saved yet.</p>
        <p className="text-xs text-ink-faint">Run a query, then save it from the results view.</p>
      </div>
    </div>
  );
}
