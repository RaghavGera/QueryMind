import { useEffect, useRef, useState } from "react";
import { useInView } from "framer-motion";
import { useReducedMotion } from "../hooks/useReducedMotion";
import { easeOutCubic } from "./math";
import { scrambleText } from "./scramble";
import { cn } from "../lib/utils";

/**
 * Text that decodes out of scrambled glyphs, on mount or when scrolled into
 * view. The final text reserves the space (no layout shift) and is what
 * screen readers get.
 */
export default function ScrambleText({
  text,
  as: Tag = "span",
  className,
  innerClassName,
  duration = 1100,
  delay = 0,
  trigger = "view",
}) {
  const reduced = useReducedMotion();
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-10% 0px" });
  const [shown, setShown] = useState(() => (reduced ? text : scrambleText(text, 0, 1)));
  const started = trigger === "mount" || inView;

  useEffect(() => {
    if (reduced || !started) return undefined;
    let raf;
    let frame = 0;
    const t0 = performance.now() + delay;
    const tick = (now) => {
      const p = Math.max(0, now - t0) / duration;
      frame += 1;
      setShown(p >= 1 ? text : scrambleText(text, easeOutCubic(Math.min(1, p)), Math.floor(frame / 2)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    // Settle on the real text even if frames are throttled (busy GPU, background tab).
    const settle = window.setTimeout(() => setShown(text), delay + duration + 80);
    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(settle);
    };
  }, [text, reduced, started, duration, delay]);

  return (
    <Tag ref={ref} className={className} aria-label={text}>
      <span aria-hidden="true" className="relative inline-block">
        <span className="invisible">{text}</span>
        <span className={cn("absolute inset-0", innerClassName)}>{reduced ? text : shown}</span>
      </span>
    </Tag>
  );
}
