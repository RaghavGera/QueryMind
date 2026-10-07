import { AnimatePresence, motion } from "framer-motion";
import { useWarpPhase, WARP_TIMINGS } from "./warp";

/**
 * The flash that carries you from the site into the app. Lives at the app
 * root so it survives the route change: grows during "in", fades during "out".
 */
export default function WarpOverlay() {
  const phase = useWarpPhase();

  return (
    <AnimatePresence>
      {phase !== "idle" && (
        <motion.div
          key="warp"
          className="pointer-events-none fixed inset-0 z-[100] overflow-hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: phase === "in" ? 1 : 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: phase === "in" ? WARP_TIMINGS.in : WARP_TIMINGS.out, ease: [0.7, 0, 0.3, 1] }}
          aria-hidden="true"
        >
          {/* Hyperspace streaks radiating from the centre. */}
          <motion.div
            className="absolute left-1/2 top-1/2 h-[220vmax] w-[220vmax] -translate-x-1/2 -translate-y-1/2"
            style={{
              background:
                "repeating-conic-gradient(from 0deg, rgba(201,194,255,0.55) 0deg 0.35deg, transparent 0.35deg 4.5deg)",
              maskImage: "radial-gradient(circle, transparent 6%, black 30%, transparent 70%)",
              WebkitMaskImage: "radial-gradient(circle, transparent 6%, black 30%, transparent 70%)",
            }}
            initial={{ scale: 0.4, rotate: 0 }}
            animate={{ scale: phase === "in" ? 1.6 : 2.4, rotate: 8 }}
            transition={{ duration: WARP_TIMINGS.in + WARP_TIMINGS.out, ease: "easeIn" }}
          />
          {/* The flash. */}
          <motion.div
            className="absolute inset-0"
            style={{ background: "radial-gradient(circle at center, #ffffff 0%, #c9c2ff 18%, #8b7bff 40%, #07070b 75%)" }}
            initial={{ scale: 0.2, opacity: 0 }}
            animate={{ scale: phase === "in" ? 2.2 : 3, opacity: phase === "in" ? 1 : 0 }}
            transition={{ duration: phase === "in" ? WARP_TIMINGS.in : WARP_TIMINGS.out, ease: [0.7, 0, 0.3, 1] }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
