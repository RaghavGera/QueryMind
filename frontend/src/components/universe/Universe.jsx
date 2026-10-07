import { Suspense, lazy, useEffect, useState } from "react";
import { useScroll, useMotionValueEvent } from "framer-motion";
import { hasWebGL } from "../../lib/webgl";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import { resetUniverse, universe } from "./universeState";

// three.js and the scene load lazily, only on the landing page.
const UniverseCanvas = lazy(() => import("./UniverseCanvas"));

/** Mounts the WebGL universe (or nothing: the layout's CSS nebula is the fallback). */
export default function Universe() {
  const [webgl] = useState(() => hasWebGL());
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll();

  useMotionValueEvent(scrollYProgress, "change", (v) => {
    universe.travel = v;
  });
  useEffect(() => resetUniverse, []);

  if (!webgl) return null;
  return (
    <Suspense fallback={null}>
      <UniverseCanvas reducedMotion={reduced} />
    </Suspense>
  );
}
