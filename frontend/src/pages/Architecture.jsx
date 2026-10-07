import { useRef, useState } from "react";
import { motion, useMotionValueEvent, useScroll, useSpring } from "framer-motion";
import { cn } from "../lib/utils";
import { architectureSteps } from "../data/mockData";
import ScrambleText from "../motion/ScrambleText";

/**
 * The ten pipeline stages on a vertical light beam. As you scroll, a pulse
 * travels down and each stage lights up (and expands) as the pulse passes.
 */
function Beam() {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 65%", "end 45%"] });
  const fill = useSpring(scrollYProgress, { stiffness: 120, damping: 24, mass: 0.4 });
  const [active, setActive] = useState(-1);
  useMotionValueEvent(scrollYProgress, "change", (v) =>
    setActive(Math.min(architectureSteps.length - 1, Math.floor(v * architectureSteps.length + 0.15))),
  );

  return (
    <div ref={ref} className="relative mx-auto max-w-3xl px-6 pb-40">
      <div className="absolute bottom-40 left-[2.15rem] top-0 w-px bg-white/[0.08] sm:left-1/2" aria-hidden="true">
        <motion.div
          style={{ scaleY: fill }}
          className="h-full w-full origin-top bg-gradient-to-b from-accent-cyan via-accent-violet to-accent-magenta shadow-[0_0_14px_rgba(94,234,212,0.8)]"
        />
      </div>

      <ol className="relative space-y-10 sm:space-y-16">
        {architectureSteps.map((step, i) => {
          const lit = i <= active;
          const current = i === active;
          const right = i % 2 === 1;
          return (
            <li key={step.key} className={cn("relative pl-12 sm:w-1/2 sm:pl-0", right ? "sm:ml-auto sm:pl-12" : "sm:pr-12 sm:text-right")}>
              <span
                className={cn(
                  "absolute top-1.5 h-3.5 w-3.5 rounded-full border transition-all duration-500",
                  "left-[1.7rem] sm:left-auto",
                  right ? "sm:-left-[0.45rem]" : "sm:-right-[0.45rem]",
                  lit ? "border-accent-cyan bg-accent-cyan shadow-[0_0_18px_rgba(94,234,212,0.9)]" : "border-white/25 bg-base-950",
                )}
                aria-hidden="true"
              />
              <p className={cn("font-mono text-[11px] tracking-[0.2em] transition-colors duration-500", lit ? "text-accent-cyan" : "text-ink-faint")}>
                {String(i + 1).padStart(2, "0")}
              </p>
              <h3 className={cn("mt-1 font-display text-2xl transition-colors duration-500 sm:text-3xl", lit ? "text-ink" : "text-ink-faint")}>
                {step.label}
              </h3>
              <motion.p
                initial={false}
                animate={{ opacity: current ? 1 : lit ? 0.75 : 0.35, height: "auto" }}
                transition={{ duration: 0.4 }}
                className="mt-2 text-sm leading-relaxed text-ink-dim sm:text-base"
              >
                {step.detail}
              </motion.p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default function Architecture() {
  return (
    <>
      <section className="mx-auto flex min-h-[70svh] max-w-4xl flex-col items-center justify-center px-6 pt-28 text-center">
        <p className="hud-label mb-6">How it works</p>
        <ScrambleText as="h1" text="From question to answer." trigger="mount" className="display-lg block" innerClassName="text-gradient" />
        <p className="mx-auto mt-6 max-w-xl text-lg text-ink-dim">
          Ten stages, each with one job. Scroll and follow the beam: every question takes this path.
        </p>
      </section>
      <Beam />
    </>
  );
}
