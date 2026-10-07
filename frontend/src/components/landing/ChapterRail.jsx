import { motion, useScroll } from "framer-motion";
import { cn } from "../../lib/utils";
import { useActiveChapter } from "../../motion/chapters";
import { useScrollTo } from "../../motion/SmoothScroll";

export const CHAPTERS = [
  { id: "boot", label: "Boot" },
  { id: "question", label: "Question" },
  { id: "schema", label: "Schema" },
  { id: "ambiguity", label: "Ambiguity" },
  { id: "sql", label: "SQL" },
  { id: "answer", label: "Answer" },
  { id: "safety", label: "Safety" },
  { id: "try", label: "Try it" },
  { id: "launch", label: "Launch" },
];

/** Fixed side rail (chapter list) + bottom-left HUD readout. Desktop only. */
export default function ChapterRail() {
  const active = useActiveChapter() ?? "boot";
  const scrollTo = useScrollTo();
  const { scrollYProgress } = useScroll();
  const index = Math.max(0, CHAPTERS.findIndex((c) => c.id === active));

  return (
    <>
      <nav aria-label="Chapters" className="fixed right-6 top-1/2 z-40 hidden -translate-y-1/2 lg:block">
        <ol className="flex flex-col items-end gap-3">
          {CHAPTERS.map((chapter, i) => {
            const isActive = chapter.id === active;
            return (
              <li key={chapter.id}>
                <button
                  onClick={() => scrollTo(`#${chapter.id}`)}
                  className="group flex items-center gap-3"
                  aria-current={isActive ? "step" : undefined}
                >
                  <span
                    className={cn(
                      "font-mono text-[10px] uppercase tracking-[0.2em] transition-all duration-300",
                      // Names show on hover only, so they never sit on top of the content.
                      isActive ? "text-accent-cyan opacity-0 group-hover:opacity-100" : "text-ink-faint opacity-0 group-hover:opacity-100",
                    )}
                  >
                    {String(i).padStart(2, "0")} {chapter.label}
                  </span>
                  <span
                    className={cn(
                      "block h-px transition-all duration-300",
                      isActive ? "w-8 bg-accent-cyan shadow-[0_0_10px_rgba(94,234,212,0.9)]" : "w-4 bg-white/25 group-hover:w-6",
                    )}
                  />
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <div className="pointer-events-none fixed bottom-6 left-6 z-40 hidden w-56 lg:block" aria-hidden="true">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-faint">
          QM/OBS · CH {String(index).padStart(2, "0")} — <span className="text-ink-dim">{CHAPTERS[index].label}</span>
        </p>
        <div className="mt-2 h-px w-full bg-white/10">
          <motion.div style={{ scaleX: scrollYProgress }} className="h-full origin-left bg-gradient-to-r from-accent-violet to-accent-cyan" />
        </div>
      </div>
    </>
  );
}
