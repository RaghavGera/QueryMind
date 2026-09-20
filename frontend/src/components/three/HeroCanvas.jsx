import { Suspense, lazy, useState } from "react";
import { hasWebGL } from "../../lib/webgl";
import { useReducedMotion } from "../../hooks/useReducedMotion";

const NetworkScene = lazy(() => import("./NetworkScene"));

export default function HeroCanvas({ className }) {
  const [webgl] = useState(() => hasWebGL());
  const reducedMotion = useReducedMotion();

  if (!webgl) {
    return (
      <div className={className}>
        <div className="h-full w-full bg-radial-glow" />
      </div>
    );
  }

  return (
    <div className={className}>
      <Suspense fallback={<div className="h-full w-full bg-radial-glow" />}>
        <NetworkScene reducedMotion={reducedMotion} />
      </Suspense>
    </div>
  );
}
