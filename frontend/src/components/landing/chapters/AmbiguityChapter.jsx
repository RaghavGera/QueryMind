import { useState } from "react";
import { motion, useMotionValueEvent, useTransform } from "framer-motion";
import { cn } from "../../../lib/utils";
import PinnedChapter, { useChapterProgress, useSegment } from "../../../motion/PinnedChapter";
import { bump } from "../../../motion/math";
import { Appear, ChapterHeading, useUniverseSignal } from "./shared";

// Verbatim from app/ambiguity_detector.py (ranking word without a metric).
const CLARIFICATION = "What should 'top' be ranked by? For example total spending, number of orders, or units sold.";
const OPTIONS = ["total spending", "number of orders", "units sold"];
// Branch end points in a 600×120 box; "top" sits at the top centre.
const ENDS = [100, 300, 500];

function Branch({ x, index }) {
  const draw = useSegment(0.24 + index * 0.05, 0.42 + index * 0.05);
  return (
    <motion.path
      d={`M300 0 C300 60, ${x} 50, ${x} 120`}
      fill="none"
      stroke="url(#amber-beam)"
      strokeWidth="1.5"
      style={{ pathLength: draw }}
    />
  );
}

function Ambiguity() {
  useUniverseSignal("amber", (p) => bump(p, 0.04, 0.2, 0.84, 1));
  const progress = useChapterProgress();
  const [glitching, setGlitching] = useState(false);
  useMotionValueEvent(progress, "change", (p) => setGlitching(p > 0.12 && p < 0.5));
  const topScale = useTransform(progress, [0.08, 0.2], [1, 1.12]);

  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col items-center justify-center px-6 pt-12 text-center">
      <ChapterHeading index="03" label="Ambiguity" title="Ambiguity is a feature." tone="amber" align="center" />

      <div className="mt-10 grid w-full grid-cols-[1fr_auto_1fr] items-baseline gap-[0.3em] whitespace-nowrap font-display text-[21px] text-ink sm:mt-12 sm:text-4xl">
        <span className="text-right text-ink-dim">“Show me the</span>
        <motion.span style={{ scale: topScale }} className="relative inline-block px-1 text-accent-amber [text-shadow:0_0_24px_rgba(251,191,36,0.6)]">
          top
          {glitching && (
            <>
              <span className="absolute inset-0 animate-glitch text-accent-cyan opacity-70 mix-blend-screen" aria-hidden="true">
                top
              </span>
              <span className="absolute inset-0 animate-glitch text-accent-magenta opacity-60 mix-blend-screen [animation-delay:-0.2s]" aria-hidden="true">
                top
              </span>
            </>
          )}
        </motion.span>
        <span className="text-left text-ink-dim">customers.”</span>
      </div>

      <div className="relative mt-2 w-full max-w-[600px]">
        <svg viewBox="0 0 600 120" className="h-[90px] w-full sm:h-[120px]" aria-hidden="true">
          <defs>
            {/* userSpaceOnUse: a bounding-box gradient vanishes on the perfectly vertical middle branch. */}
            <linearGradient id="amber-beam" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="120">
              <stop offset="0" stopColor="#fbbf24" stopOpacity="0.9" />
              <stop offset="1" stopColor="#fbbf24" stopOpacity="0.25" />
            </linearGradient>
          </defs>
          {ENDS.map((x, i) => (
            <Branch key={x} x={x} index={i} />
          ))}
        </svg>
        <div className="grid grid-cols-3 gap-2">
          {OPTIONS.map((option, i) => (
            <Appear key={option} at={0.36 + i * 0.05}>
              <span className={cn("chip inline-block !border-accent-amber/30 !bg-accent-amber/10 !px-3 !py-1.5 font-mono !text-[11px] !text-accent-amber sm:!text-[12px]")}>
                {option}
              </span>
            </Appear>
          ))}
        </div>
      </div>

      <Appear at={0.56} className="mt-10 w-full max-w-xl">
        <div className="hud hud-amber p-6 text-left">
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-accent-amber">I need one detail</p>
          <p className="mt-2 text-lg leading-snug text-ink">{CLARIFICATION}</p>
          <div className="mt-4 rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-ink-faint">
            Type your clarification…
          </div>
        </div>
      </Appear>

      <Appear at={0.7} className="mt-6 font-mono text-[12px] uppercase tracking-[0.18em] text-ink-faint">
        Instead of guessing, QueryMind asks. Then it runs exactly what you meant.
      </Appear>
    </div>
  );
}

export default function AmbiguityChapter() {
  return (
    <PinnedChapter id="ambiguity" length={2.6}>
      <Ambiguity />
    </PinnedChapter>
  );
}
