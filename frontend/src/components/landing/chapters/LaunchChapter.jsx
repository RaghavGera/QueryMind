import { Link } from "react-router-dom";
import { motion, useTransform } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import PinnedChapter, { useChapterProgress } from "../../../motion/PinnedChapter";
import Magnetic from "../../../motion/Magnetic";
import ScrambleText from "../../../motion/ScrambleText";
import { segment } from "../../../motion/math";
import { useLaunch } from "../../../motion/warp";
import { useUniverseSignal } from "./shared";

function Launch() {
  // Scrolling here already bends the stars into streaks; the button finishes the jump.
  useUniverseSignal("warp", (p) => segment(p, 0.15, 0.9) * 0.5);
  const progress = useChapterProgress();
  const launch = useLaunch();
  const scale = useTransform(progress, [0, 1], [0.92, 1.08]);

  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(ellipse 55% 40% at center, rgba(5,5,10,0.65), transparent 70%)" }}
      />
      <p className="hud-label relative mb-6">08 — Launch</p>
      <motion.div style={{ scale }} className="relative">
        <ScrambleText as="h2" text="Ready when you are." className="display-xl block" innerClassName="text-gradient" />
      </motion.div>
      <p className="relative mt-6 max-w-md text-ink-dim">
        Ask your first question. QueryMind will ask you one back if it needs to.
      </p>
      <div className="relative mt-10 flex flex-col items-center gap-4">
        <Magnetic strength={0.35}>
          <button onClick={() => launch("/app")} className="btn-primary !px-9 !py-4 text-base">
            Launch QueryMind <ArrowUpRight size={18} />
          </button>
        </Magnetic>
        <Link to="/app" className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint hover:text-ink">
          or open the app without the warp
        </Link>
      </div>
    </div>
  );
}

export default function LaunchChapter() {
  return (
    <PinnedChapter id="launch" length={2}>
      <Launch />
    </PinnedChapter>
  );
}
