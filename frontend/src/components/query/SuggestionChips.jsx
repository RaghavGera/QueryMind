export default function SuggestionChips({ items, onPick }) {
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {items.map((q) => (
        <button
          key={q}
          onClick={() => onPick(q)}
          className="chip transition-colors hover:border-line-strong hover:text-ink hover:bg-white/[0.05]"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
