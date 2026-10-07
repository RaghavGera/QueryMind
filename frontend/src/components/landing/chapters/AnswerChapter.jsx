import { motion, useTransform } from "framer-motion";
import PinnedChapter, { useChapterProgress, useSegment } from "../../../motion/PinnedChapter";
import CountUp from "../../../motion/CountUp";
import { bump } from "../../../motion/math";
import { Appear, ChapterHeading, useUniverseSignal } from "./shared";

// Real output of the showcase query (grouped by country) on the QueryMind
// demo database, captured 2026-10-07. India's total matches the live check.
const REVENUE = [
  { country: "India", value: 734561 },
  { country: "UK", value: 688224 },
  { country: "Australia", value: 664939 },
  { country: "Canada", value: 658418 },
  { country: "USA", value: 651878 },
];
const MAX = REVENUE[0].value;

function Bar({ row, index }) {
  const progress = useChapterProgress();
  const grow = useTransform(progress, [0.22 + index * 0.05, 0.5 + index * 0.05], [0, 1], { clamp: true });
  const width = useTransform(grow, (g) => `${g * (row.value / MAX) * 100}%`);
  return (
    <div className="grid grid-cols-[84px_1fr_92px] items-center gap-3 text-sm sm:grid-cols-[100px_1fr_100px]">
      <span className={index === 0 ? "text-ink" : "text-ink-dim"}>{row.country}</span>
      {/* Bars start at zero: the countries really are this close. */}
      <div className="h-3 overflow-hidden rounded-full bg-white/[0.05]">
        <motion.div
          style={{ width }}
          className={
            index === 0
              ? "h-full rounded-full bg-gradient-to-r from-accent-violet to-accent-magenta shadow-[0_0_16px_rgba(244,114,182,0.6)]"
              : "h-full rounded-full bg-gradient-to-r from-accent-violet/70 to-accent-violet/40"
          }
        />
      </div>
      <CountUp progress={grow} to={row.value} className="text-right font-mono text-[12px] text-ink-dim" />
    </div>
  );
}

function Answer() {
  useUniverseSignal("magenta", (p) => bump(p, 0.04, 0.2, 0.84, 1));
  const total = useSegment(0.14, 0.5);

  return (
    <div className="mx-auto grid h-full max-w-7xl grid-cols-1 content-center items-center gap-8 px-5 pt-16 sm:gap-12 sm:px-6 lg:grid-cols-2 lg:gap-16">
      <div>
        <ChapterHeading index="05" label="The answer" title="Answers, with the receipts." tone="magenta" />
        <Appear at={0.12} className="mt-10">
          <p className="hud-label text-accent-magenta">Highest revenue · demo database</p>
          <div className="mt-3 flex flex-wrap items-baseline gap-x-5 gap-y-1">
            <span className="display-md text-ink">India</span>
            <CountUp
              progress={total}
              to={734561}
              className="font-display font-semibold tracking-tight text-gradient-neon [font-size:clamp(2.75rem,6vw,5.5rem)]"
            />
          </div>
        </Appear>
      </div>

      <Appear at={0.18}>
        <div className="hud p-6 sm:p-7">
          <div className="mb-5 flex items-center justify-between">
            <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">Revenue by country</span>
            <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">5 rows</span>
          </div>
          <div className="space-y-4">
            {REVENUE.map((row, i) => (
              <Bar key={row.country} row={row} index={i} />
            ))}
          </div>
          <p className="mt-6 border-t border-white/[0.06] pt-4 text-xs leading-relaxed text-ink-faint">
            Example run on the QueryMind demo database (500 customers, 2,000 orders). Every answer comes with the SQL that
            produced it.
          </p>
        </div>
      </Appear>
    </div>
  );
}

export default function AnswerChapter() {
  return (
    <PinnedChapter id="answer" length={2.2}>
      <Answer />
    </PinnedChapter>
  );
}
