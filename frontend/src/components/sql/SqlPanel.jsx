import { useState } from "react";
import { motion } from "framer-motion";
import { Copy, Check, RefreshCcw, Sparkles, ChevronDown } from "lucide-react";
import { highlightSqlLine } from "../../lib/sqlHighlight";
import { cn } from "../../lib/utils";

export default function SqlPanel({ sql, dialect = "PostgreSQL", onRerun, onExplain }) {
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const lines = sql.split("\n");

  const copy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="surface-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <button onClick={() => setCollapsed((c) => !c)} className="flex items-center gap-2 text-sm text-ink">
          <ChevronDown size={14} className={cn("transition-transform", collapsed && "-rotate-90")} />
          Generated SQL
        </button>
        <span className="chip">{dialect}</span>
      </div>

      {!collapsed && (
        <>
          <div className="max-h-72 overflow-auto px-4 py-3">
            <pre className="mono text-[13px] leading-relaxed">
              {lines.map((line, i) => (
                <div key={i} className="flex gap-4">
                  <span className="select-none text-right text-ink-faint" style={{ width: 20 }}>
                    {i + 1}
                  </span>
                  <code>
                    {highlightSqlLine(line).map((tok, j) => (
                      <span key={j} className={tok.cls}>
                        {tok.text}
                      </span>
                    ))}
                  </code>
                </div>
              ))}
            </pre>
          </div>

          <div className="flex items-center gap-1 border-t border-line px-3 py-2">
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
                Run again
              </button>
            )}
          </div>
        </>
      )}
    </motion.div>
  );
}
