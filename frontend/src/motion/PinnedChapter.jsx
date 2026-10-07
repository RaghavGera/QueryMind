import { createContext, useContext, useRef } from "react";
import { useMotionValue, useMotionValueEvent, useScroll, useTransform } from "framer-motion";
import { cn } from "../lib/utils";
import { useChapterSpy } from "./chapters";

const ChapterProgress = createContext(null);

/**
 * A scene that pins to the screen for ``length`` screen-heights of scrolling.
 * Children read the 0..1 scroll progress through useChapterProgress /
 * useSegment, so animations are scrubbed by scroll (and rewind on scroll-up).
 */
export default function PinnedChapter({ id, length = 2, className, children }) {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  // Re-publish as a plain motion value. Passed straight through, framer-motion
  // hands opacity/transform to a native ViewTimeline, whose progress for a
  // pinned (sticky) section differs from the offsets above (measured: an
  // element meant to be fully visible at 80% sat at 25% opacity).
  const progress = useMotionValue(0);
  useMotionValueEvent(scrollYProgress, "change", (v) => progress.set(v));
  useChapterSpy(ref, id);

  return (
    <section ref={ref} id={id} className="chapter relative" style={{ "--len": length }}>
      <div className={cn("sticky top-0 h-svh overflow-hidden", className)}>
        <ChapterProgress.Provider value={progress}>{children}</ChapterProgress.Provider>
      </div>
    </section>
  );
}

export function useChapterProgress() {
  return useContext(ChapterProgress);
}

/** 0..1 motion value for the [start, end] window of the current chapter. */
export function useSegment(start, end) {
  return useTransform(useChapterProgress(), [start, end], [0, 1], { clamp: true });
}
