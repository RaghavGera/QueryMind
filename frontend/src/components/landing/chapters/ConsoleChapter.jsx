import { useRef } from "react";
import { useChapterSpy } from "../../../motion/chapters";
import InteractiveDemo from "../InteractiveDemo";
import { ChapterHeading } from "./shared";

/** Not pinned: a normal section so typing and reading results feel native. */
export default function ConsoleChapter() {
  const ref = useRef(null);
  useChapterSpy(ref, "try");

  return (
    <section ref={ref} id="try" className="relative mx-auto max-w-4xl px-6 py-32">
      <ChapterHeading index="07" label="Try it" title="Ask it yourself." align="center">
        This console is live: it sends your question to the real QueryMind API and runs it on the demo database.
      </ChapterHeading>
      <div className="hud mt-12 p-4 sm:p-6">
        <div className="mb-4 flex items-center justify-between border-b border-white/[0.06] pb-3">
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">querymind://console</span>
          <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-accent-cyan">
            <span className="status-dot animate-pulse-glow bg-accent-cyan" /> live api
          </span>
        </div>
        <InteractiveDemo />
      </div>
    </section>
  );
}
