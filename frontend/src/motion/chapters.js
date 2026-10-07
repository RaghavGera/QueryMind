import { useEffect, useSyncExternalStore } from "react";

// Which landing chapter is under the middle of the screen (for the side rail).
let active = null;
const listeners = new Set();

function setActive(id) {
  if (id === active) return;
  active = id;
  listeners.forEach((fn) => fn());
}

export function useActiveChapter() {
  return useSyncExternalStore(
    (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    () => active,
    () => null,
  );
}

/** Mark ``ref``'s element as chapter ``id`` while it crosses the screen's middle. */
export function useChapterSpy(ref, id) {
  useEffect(() => {
    const el = ref.current;
    if (!el || !id || typeof IntersectionObserver === "undefined") return undefined;
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => entry.isIntersecting && setActive(id)),
      { rootMargin: "-50% 0px -50% 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, id]);
}
