import { useMemo, useState } from "react";
import { motion, useMotionValueEvent, useTransform } from "framer-motion";
import { cn } from "../../../lib/utils";
import { highlightSqlLine } from "../../../lib/sqlHighlight";
import { visibleChars } from "../../../motion/math";
import { sliceLines } from "../../../motion/text";
import ScrambleText from "../../../motion/ScrambleText";
import { useChapterProgress } from "../../../motion/PinnedChapter";
import { universe } from "../../universe/universeState";

/** "01 — The question" label + decoding title + body copy. */
export function ChapterHeading({ index, label, title, children, tone = "cyan", align = "left", compact = false, className }) {
  return (
    <div className={cn(align === "center" && "text-center", className)}>
      <p className={cn("hud-label mb-5", tone === "amber" && "text-accent-amber", tone === "magenta" && "text-accent-magenta")}>
        {index} — {label}
      </p>
      <ScrambleText as="h2" text={title} className="display-lg block" innerClassName="text-gradient" />
      {children && (
        <div
          className={cn(
            "mt-6 max-w-md text-base leading-relaxed text-ink-dim sm:text-lg",
            align === "center" && "mx-auto",
            compact && "max-sm:hidden", // phones: the scene speaks for itself
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}

/** Writes ``map(chapterProgress)`` into universe[key] (the 3D scene reads it). */
export function useUniverseSignal(key, map) {
  const progress = useChapterProgress();
  useMotionValueEvent(progress, "change", (p) => {
    universe[key] = map(p);
  });
}

/** Fades/slides children in when the chapter passes ``at`` (scrubbed). */
export function Appear({ at, span = 0.08, y = 18, x = 0, className, children }) {
  const progress = useChapterProgress();
  const opacity = useTransform(progress, [at, at + span], [0, 1]);
  const ty = useTransform(progress, [at, at + span], [y, 0]);
  const tx = useTransform(progress, [at, at + span], [x, 0]);
  return (
    <motion.div style={{ opacity, y: ty, x: tx }} className={className}>
      {children}
    </motion.div>
  );
}

/** SQL typed by a 0..1 motion value, syntax-highlighted as it appears. */
export function TypedCode({ progress, code, className, highlight = highlightSqlLine, numbers = true }) {
  const lines = useMemo(() => code.split("\n").map((line) => highlight(line)), [code, highlight]);
  const total = code.length;
  const [count, setCount] = useState(() => visibleChars(progress.get(), total));
  useMotionValueEvent(progress, "change", (v) => setCount(visibleChars(v, total)));

  return (
    <pre className={cn("mono whitespace-pre-wrap break-words text-[12.5px] leading-relaxed sm:text-[13px]", className)} aria-label={code}>
      <code aria-hidden="true">
        {sliceLines(lines, count).map((tokens, i) => (
          <div key={i} className="flex gap-4">
            {numbers && <span className="w-5 shrink-0 select-none text-right text-ink-faint">{i + 1}</span>}
            <span className="min-w-0">
              {tokens.map((tok, j) => (
                <span key={j} className={tok.cls}>
                  {tok.text}
                </span>
              ))}
            </span>
          </div>
        ))}
        {count < total && <span className={cn("inline-block h-4 w-2 translate-y-0.5 animate-caret bg-accent-cyan", numbers && "ml-9")} />}
      </code>
    </pre>
  );
}
