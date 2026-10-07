import { useRef } from "react";
import { motion, useSpring } from "framer-motion";
import { useReducedMotion } from "../hooks/useReducedMotion";
import { cn } from "../lib/utils";

/** Pulls its child gently toward the pointer (CTAs). Static under reduced motion. */
export default function Magnetic({ children, strength = 0.28, className }) {
  const reduced = useReducedMotion();
  const ref = useRef(null);
  const x = useSpring(0, { stiffness: 260, damping: 18, mass: 0.4 });
  const y = useSpring(0, { stiffness: 260, damping: 18, mass: 0.4 });

  if (reduced) return <div className={cn("inline-block", className)}>{children}</div>;

  const onMove = (event) => {
    const rect = ref.current.getBoundingClientRect();
    x.set((event.clientX - (rect.left + rect.width / 2)) * strength);
    y.set((event.clientY - (rect.top + rect.height / 2)) * strength);
  };
  const reset = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.div ref={ref} style={{ x, y }} onPointerMove={onMove} onPointerLeave={reset} className={cn("inline-block", className)}>
      {children}
    </motion.div>
  );
}
