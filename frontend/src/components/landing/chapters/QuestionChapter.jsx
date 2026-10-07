import { useState } from "react";
import { useMotionValueEvent } from "framer-motion";
import { CornerDownRight, Sparkles } from "lucide-react";
import PinnedChapter, { useChapterProgress, useSegment } from "../../../motion/PinnedChapter";
import ScrollTyped from "../../../motion/ScrollTyped";
import { Appear, ChapterHeading } from "./shared";

export const QUESTION = "Which region generated the most revenue?";
const ENTITIES = {
  region: "text-accent-cyan [text-shadow:0_0_18px_rgba(94,234,212,0.7)]",
  revenue: "text-accent-glow [text-shadow:0_0_18px_rgba(167,139,250,0.75)]",
};

function Question() {
  const typing = useSegment(0.08, 0.55);
  const progress = useChapterProgress();
  const [lit, setLit] = useState(false);
  useMotionValueEvent(progress, "change", (p) => setLit(p > 0.6));

  return (
    <div className="mx-auto grid h-full max-w-7xl grid-cols-1 content-center items-center gap-10 px-5 pt-16 sm:px-6 lg:grid-cols-[5fr_7fr] lg:gap-16">
      <ChapterHeading index="01" label="The question" title="It starts with plain English.">
        No SQL. No table names. Ask the way you&apos;d ask a colleague.
      </ChapterHeading>

      <div className="min-w-0 space-y-6">
        <div className="hud flex items-center gap-4 px-6 py-5 sm:px-7 sm:py-6">
          <Sparkles size={20} className="shrink-0 text-accent-violet" />
          <ScrollTyped
            progress={typing}
            text={QUESTION}
            highlights={ENTITIES}
            lit={lit}
            className="font-display text-xl text-ink sm:text-2xl lg:text-[28px]"
          />
        </div>

        <div className="flex flex-wrap gap-3">
          <Appear at={0.6} className="chip !border-accent-cyan/30 !bg-accent-cyan/10 !px-4 !py-2 font-mono !text-[12px] !text-accent-cyan">
            region · a place
          </Appear>
          <Appear at={0.66} className="chip !border-accent-violet/30 !bg-accent-violet/10 !px-4 !py-2 font-mono !text-[12px] !text-accent-glow">
            revenue · a metric
          </Appear>
        </div>

        <Appear at={0.76} className="flex items-center gap-2 font-mono text-[12px] uppercase tracking-[0.18em] text-ink-faint">
          <CornerDownRight size={14} className="text-accent-cyan" />
          handing the question to the intent extractor
        </Appear>
      </div>
    </div>
  );
}

export default function QuestionChapter() {
  return (
    <PinnedChapter id="question" length={2.2}>
      <Question />
    </PinnedChapter>
  );
}
