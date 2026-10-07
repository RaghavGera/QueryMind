import { useState } from "react";
import { motion } from "framer-motion";

export default function ClarificationPanel({
  question,
  questions = [],
  onSelect,
  selectedId,
}) {
  const [answer, setAnswer] = useState("");

  const submit = (event) => {
    event.preventDefault();

    if (answer.trim()) {
      onSelect(answer.trim());
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="hud hud-amber p-5"
    >
      <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.22em] text-accent-amber">
        I need one detail
      </p>

      <h3 className="mb-3 text-lg font-medium text-ink">{question}</h3>

      {questions.length > 1 && (
        <ul className="mb-4 list-disc space-y-1 pl-5 text-sm text-ink-dim">
          {questions.slice(1).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}

      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
        <input
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          disabled={!!selectedId}
          placeholder="Type your clarification..."
          className="min-w-0 flex-1 rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-ink caret-accent-amber outline-none placeholder:text-ink-faint focus:border-accent-amber/50"
          autoFocus
        />

        <button
          type="submit"
          disabled={!answer.trim() || !!selectedId}
          className="btn-primary shrink-0 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Continue
        </button>
      </form>
    </motion.div>
  );
}
