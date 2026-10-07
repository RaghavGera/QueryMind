import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { cn } from "../../lib/utils";

function useElapsed(startedAt) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(id);
  }, []);
  return startedAt ? Math.max(0, now - startedAt) : 0;
}

/**
 * Shown while the backend works. Honest by design: the stage names describe
 * the pipeline the question travels through; nothing here claims a stage has
 * finished. The timer is real elapsed time.
 */
export default function PipelineBeam({ stages, startedAt, label = "Working" }) {
  const elapsed = useElapsed(startedAt);
  const slow = elapsed > 8000;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="hud px-5 py-4" role="status" aria-live="polite">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.22em] text-accent-cyan">
          <span className="status-dot animate-pulse-glow bg-accent-cyan" />
          {label}
        </span>
        <span className="font-mono text-[12px] tabular-nums text-ink-dim">{(elapsed / 1000).toFixed(1)} s</span>
      </div>

      <div className="relative mt-4 h-px w-full overflow-hidden bg-white/[0.08]">
        <span className="absolute inset-y-0 left-0 w-1/4 animate-beam bg-gradient-to-r from-transparent via-accent-cyan to-transparent shadow-[0_0_12px_rgba(94,234,212,0.9)]" />
      </div>

      <ol className="mt-3 grid gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-faint sm:text-[11px]" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
        {stages.map((stage, i) => (
          <li key={stage} className={cn("truncate", i === 0 && "text-left", i === stages.length - 1 && "text-right", i > 0 && i < stages.length - 1 && "text-center")}>
            {stage}
          </li>
        ))}
      </ol>

      {slow && (
        <p className="mt-3 text-xs text-ink-faint">
          Still working: the language model is taking longer than usual. Answers normally take a few seconds.
        </p>
      )}
    </motion.div>
  );
}
