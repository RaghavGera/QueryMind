export default function SuggestionChips({ items, onPick }) {
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {items.map((q) => (
        <button
          key={q}
          onClick={() => onPick(q)}
          className="chip transition-all duration-200 hover:border-accent-cyan/40 hover:bg-accent-cyan/[0.06] hover:text-ink hover:shadow-[0_0_20px_-6px_rgba(94,234,212,0.6)]"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
