import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Copy, Check, RefreshCcw, Sparkles, ChevronDown } from "lucide-react";
import { highlightSqlLine } from "../../lib/sqlHighlight";
import { cn } from "../../lib/utils";
import { sliceLines } from "../../motion/text";
import { useReducedMotion } from "../../hooks/useReducedMotion";

const TYPE_MS = 450;

/** Reveal ``length`` characters over TYPE_MS (fast enough to never be in the way). */
function useQuickType(length, enabled) {
  const [count, setCount] = useState(enabled ? 0 : length);
  useEffect(() => {
    if (!enabled) return undefined;
    let raf;
    const t0 = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / TYPE_MS);
      setCount(Math.round(p * length));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    const settle = window.setTimeout(() => setCount(length), TYPE_MS + 80);
    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(settle);
    };
  }, [length, enabled]);
  return count;
}

export default function SqlPanel({ sql, dialect = "PostgreSQL", onRerun, onExplain, rerunLabel = "Run again", animate = true }) {
  const reduced = useReducedMotion();
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const lines = useMemo(() => sql.split("\n").map((line) => highlightSqlLine(line)), [sql]);
  const count = useQuickType(sql.length, animate && !reduced);

  const copy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="hud">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
        <button onClick={() => setCollapsed((c) => !c)} className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-ink-dim hover:text-ink">
          <ChevronDown size={14} className={cn("transition-transform", collapsed && "-rotate-90")} />
          Generated SQL
        </button>
        <span className="chip font-mono !text-[10px] uppercase tracking-[0.16em]">{dialect}</span>
      </div>

      {!collapsed && (
        <>
          <div className="max-h-72 overflow-auto px-4 py-3">
            <pre className="mono text-[13px] leading-relaxed" aria-label={sql}>
              {sliceLines(lines, count).map((tokens, i) => (
                <div key={i} className="flex gap-4" aria-hidden="true">
                  <span className="select-none text-right text-ink-faint" style={{ width: 20 }}>
                    {i + 1}
                  </span>
                  <code className="whitespace-pre-wrap break-words">
                    {tokens.map((tok, j) => (
                      <span key={j} className={tok.cls}>
                        {tok.text}
                      </span>
                    ))}
                  </code>
                </div>
              ))}
            </pre>
          </div>

          <div className="flex items-center gap-1 border-t border-white/[0.06] px-3 py-2">
            <button onClick={copy} className="btn-ghost">
              {copied ? <Check size={14} className="text-state-success" /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy"}
            </button>
            {onExplain && (
              <button onClick={onExplain} className="btn-ghost">
                <Sparkles size={14} />
                Explain
              </button>
            )}
            {onRerun && (
              <button onClick={onRerun} className="btn-ghost">
                <RefreshCcw size={14} />
                {rerunLabel}
              </button>
            )}
          </div>
        </>
      )}
    </motion.div>
  );
}
