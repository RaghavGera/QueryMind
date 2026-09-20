import { motion } from "framer-motion";
import { DollarSign, TrendingUp, Target } from "lucide-react";
import { cn } from "../../lib/utils";

const icons = { dollar: DollarSign, trending: TrendingUp, target: Target };

export default function ClarificationPanel({ question, options, onSelect, selectedId }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="surface-card p-5"
    >
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-accent-glow">
        I need one detail
      </p>
      <h3 className="mb-4 text-lg font-medium text-ink">{question}</h3>

      <div className="grid gap-3 sm:grid-cols-3">
        {options.map((opt) => {
          const Icon = icons[opt.icon] ?? DollarSign;
          const selected = selectedId === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onSelect(opt.id)}
              disabled={!!selectedId}
              className={cn(
                "flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition-all duration-200",
                selected
                  ? "border-accent-violet/60 bg-accent-violet/10 shadow-glow-sm"
                  : "border-line bg-white/[0.02] hover:border-line-strong hover:bg-white/[0.05] hover:-translate-y-0.5",
                selectedId && !selected && "opacity-40"
              )}
            >
              <Icon size={18} className="text-accent-glow" />
              <span className="text-sm font-medium text-ink">{opt.label}</span>
              <span className="text-xs leading-relaxed text-ink-dim">{opt.description}</span>
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}
