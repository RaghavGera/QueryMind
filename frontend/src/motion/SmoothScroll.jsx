import { createContext, useCallback, useContext, useEffect, useRef } from "react";
import Lenis from "lenis";
import "lenis/dist/lenis.css";
import { useReducedMotion } from "../hooks/useReducedMotion";

const LenisContext = createContext({ current: null });

/**
 * Inertial smooth scrolling for the marketing pages (never inside /app).
 * Lenis drives the native scroll position, so framer-motion's useScroll and
 * sticky positioning keep working. Off when reduced motion is requested.
 */
export function SmoothScroll({ children }) {
  const reduced = useReducedMotion();
  const lenisRef = useRef(null);

  useEffect(() => {
    if (reduced) return undefined;
    const lenis = new Lenis({ autoRaf: true, lerp: 0.085, smoothWheel: true, wheelMultiplier: 0.9 });
    lenisRef.current = lenis;
    return () => {
      lenis.destroy();
      lenisRef.current = null;
    };
  }, [reduced]);

  return <LenisContext.Provider value={lenisRef}>{children}</LenisContext.Provider>;
}

/** Scroll to an element, selector or y offset: smoothly via Lenis when it runs. */
export function useScrollTo() {
  const lenisRef = useContext(LenisContext);
  return useCallback(
    (target, { immediate = false, duration = 1.6 } = {}) => {
      const lenis = lenisRef.current;
      if (lenis) {
        lenis.scrollTo(target, { immediate, duration });
        return;
      }
      const behavior = immediate ? "auto" : "smooth";
      if (typeof target === "number") {
        window.scrollTo({ top: target, behavior });
      } else {
        const el = typeof target === "string" ? document.querySelector(target) : target;
        el?.scrollIntoView({ behavior });
      }
    },
    [lenisRef],
  );
}
