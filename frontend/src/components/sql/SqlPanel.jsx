import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Copy, Check, RefreshCcw, Sparkles, ChevronDown } from "lucide-react";
import { highlightSqlLine } from "../../lib/sqlHighlight";
import { cn } from "../../lib/utils";
import { sliceLines } from "../../motion/text";
import { inlineParams } from "../../lib/sqlDisplay";
import { useReducedMotion } from "../../hooks/useReducedMotion";

const TYPE_MS = 450;
const NO_PARAMS = [];

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

export default function SqlPanel({
  sql,
  params = NO_PARAMS,
  dialect = "PostgreSQL",
  onRerun,
  onExplain,
  rerunLabel = "Run again",
  animate = true,
}) {
  const reduced = useReducedMotion();
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  // Show (and copy) the bound values in place of %s, so the query is readable
  // and runnable as displayed. The server still sends them as parameters.
  const shown = useMemo(() => inlineParams(sql, params), [sql, params]);
  const lines = useMemo(() => shown.split("\n").map((line) => highlightSqlLine(line)), [shown]);
  const count = useQuickType(shown.length, animate && !reduced);
  const hasParams = params.length > 0;

  const copy = async () => {
    await navigator.clipboard.writeText(shown);
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
            <pre className="mono text-[13px] leading-relaxed" aria-label={shown}>
              {sliceLines(lines, count).map((tokens, i) => (
                <div key={i} className="flex gap-4" aria-hidden="true">
                  <span className="w-5 shrink-0 select-none text-right text-ink-faint">
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
            {hasParams && (
              <span
                className="ml-auto hidden font-mono text-[10px] uppercase tracking-[0.16em] text-ink-faint sm:inline"
                title="The values are shown in place; the server sends them separately as query parameters."
              >
                {params.length} parameter{params.length === 1 ? "" : "s"} shown inline
              </span>
            )}
          </div>
        </>
      )}
    </motion.div>
  );
}
