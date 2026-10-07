import { useMemo, useState } from "react";
import { useMotionValueEvent } from "framer-motion";
import { cn } from "../lib/utils";
import { visibleChars } from "./math";
import { splitHighlights, typedSegments } from "./text";

/**
 * Text typed by a 0..1 motion value (scroll-scrubbed typing). ``highlights``
 * maps words to classes applied once the word is complete and ``lit`` is on.
 */
export default function ScrollTyped({ progress, text, highlights, lit = true, caret = true, className }) {
  const [count, setCount] = useState(() => visibleChars(progress.get(), text.length));
  useMotionValueEvent(progress, "change", (v) => setCount(visibleChars(v, text.length)));
  const segments = useMemo(() => splitHighlights(text, highlights), [text, highlights]);
  const done = count >= text.length;

  return (
    <span className={className} aria-label={text}>
      <span aria-hidden="true">
        {typedSegments(segments, count).map((seg, i) => (
          <span
            key={i}
            className={cn("transition-[color,text-shadow] duration-500", lit && seg.className)}
          >
            {seg.text}
          </span>
        ))}
        {caret && (
          <span
            className={cn(
              "ml-0.5 inline-block h-[1em] w-[0.08em] translate-y-[0.12em] bg-accent-cyan shadow-[0_0_12px_rgba(94,234,212,0.9)]",
              done && "animate-caret",
            )}
          />
        )}
      </span>
    </span>
  );
}
