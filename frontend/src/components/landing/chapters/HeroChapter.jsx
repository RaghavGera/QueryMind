import { motion, useTransform } from "framer-motion";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import PinnedChapter, { useChapterProgress } from "../../../motion/PinnedChapter";
import ScrambleText from "../../../motion/ScrambleText";
import Magnetic from "../../../motion/Magnetic";
import { useLaunch } from "../../../motion/warp";
import { useScrollTo } from "../../../motion/SmoothScroll";

function Hero() {
  const progress = useChapterProgress();
  const launch = useLaunch();
  const scrollTo = useScrollTo();

  // Scrolling flies the camera *through* the title.
  const titleScale = useTransform(progress, [0, 1], [1, 1.45]);
  const titleOpacity = useTransform(progress, [0.3, 0.85], [1, 0]);
  const titleBlur = useTransform(progress, [0.3, 0.85], ["blur(0px)", "blur(16px)"]);
  const restOpacity = useTransform(progress, [0, 0.35], [1, 0]);
  const restY = useTransform(progress, [0, 0.35], [0, -36]);

  return (
    <div className="relative flex h-full flex-col items-center justify-center px-5 text-center">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(ellipse 60% 45% at center, rgba(5,5,10,0.6), transparent 70%)" }}
      />

      <motion.p style={{ opacity: restOpacity, y: restY }} className="hud-label relative mb-8 flex items-center gap-3">
        <span className="h-px w-8 bg-gradient-to-r from-transparent to-accent-cyan" />
        Natural language → safe SQL
        <span className="h-px w-8 bg-gradient-to-l from-transparent to-accent-cyan" />
      </motion.p>

      <motion.h1 style={{ scale: titleScale, opacity: titleOpacity, filter: titleBlur }} className="relative">
        <ScrambleText text="Ask your database." trigger="mount" duration={1300} className="display-xl block" innerClassName="text-gradient" />
        <ScrambleText
          text="It thinks before it queries."
          trigger="mount"
          delay={450}
          duration={1200}
          className="mt-3 block font-display font-medium tracking-[-0.02em] [font-size:clamp(1.5rem,3.4vw,3.25rem)]"
          innerClassName="text-gradient-neon"
        />
      </motion.h1>

      <motion.div style={{ opacity: restOpacity, y: restY }} className="relative">
        <p className="mx-auto mt-8 max-w-xl text-balance text-base leading-relaxed text-ink-dim sm:text-lg">
          QueryMind turns plain English into parameterized SQL, and when a question could mean two things, it asks
          instead of guessing.
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Magnetic>
            <button onClick={() => launch("/app")} className="btn-primary !px-7 !py-3.5 text-[15px]">
              Launch QueryMind <ArrowUpRight size={16} />
            </button>
          </Magnetic>
          <button onClick={() => scrollTo("#question")} className="btn-secondary !px-7 !py-3.5 text-[15px]">
            Watch it think
          </button>
        </div>
      </motion.div>

      <motion.button
        style={{ opacity: restOpacity }}
        onClick={() => scrollTo("#question")}
        className="absolute bottom-8 left-1/2 flex -translate-x-1/2 flex-col items-center gap-3"
        aria-label="Scroll to the first chapter"
      >
        <span className="hud-label text-ink-faint">Scroll to send a query</span>
        <span className="relative h-12 w-px overflow-hidden bg-white/10">
          <span className="absolute inset-0 animate-scroll-cue bg-gradient-to-b from-accent-cyan to-transparent" />
        </span>
        <ChevronDown size={14} className="text-ink-faint" />
      </motion.button>
    </div>
  );
}

export default function HeroChapter() {
  return (
    <PinnedChapter id="boot" length={1.6}>
      <Hero />
    </PinnedChapter>
  );
}
