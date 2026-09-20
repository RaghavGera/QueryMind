import { motion, AnimatePresence } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

export default function ProcessingTimeline({ stages, activeIndex }) {
  return (
    <div className="surface-card px-5 py-4">
      <ul className="space-y-2.5">
        <AnimatePresence initial={false}>
          {stages.map((stage, i) => {
            const done = i < activeIndex;
            const active = i === activeIndex;
            if (i > activeIndex) return null;
            return (
              <motion.li
                key={stage}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="flex items-center gap-3 text-sm"
              >
                <span
                  className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
                    done && "border-state-success/40 bg-state-success/10 text-state-success",
                    active && "border-accent-violet/40 bg-accent-violet/10 text-accent-glow"
                  )}
                >
                  {done ? <Check size={12} /> : <Loader2 size={12} className="animate-spin" />}
                </span>
                <span className={cn(done ? "text-ink-dim" : "text-ink")}>{stage}</span>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ul>
    </div>
  );
}
