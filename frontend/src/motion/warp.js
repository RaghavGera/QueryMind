import { useCallback, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import { universe } from "../components/universe/universeState";
import { useReducedMotion } from "../hooks/useReducedMotion";

// Full-screen "jump to hyperspace" between the site and the app.
const WARP_IN_MS = 750;
const WARP_OUT_MS = 700;

let phase = "idle"; // idle -> in (stars stretch, flash grows) -> out (flash fades over the new page)
const listeners = new Set();

function setPhase(next) {
  phase = next;
  listeners.forEach((fn) => fn());
}

export function useWarpPhase() {
  return useSyncExternalStore(
    (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    () => phase,
    () => "idle",
  );
}

/** Returns launch(to): warps then navigates; plain navigation under reduced motion. */
export function useLaunch() {
  const navigate = useNavigate();
  const reduced = useReducedMotion();
  return useCallback(
    (to = "/app") => {
      if (reduced) {
        navigate(to);
        return;
      }
      if (phase !== "idle") return;
      universe.warpBoost = 1;
      setPhase("in");
      window.setTimeout(() => {
        navigate(to);
        setPhase("out");
        window.setTimeout(() => {
          universe.warpBoost = 0;
          setPhase("idle");
        }, WARP_OUT_MS);
      }, WARP_IN_MS);
    },
    [navigate, reduced],
  );
}

export const WARP_TIMINGS = { in: WARP_IN_MS / 1000, out: WARP_OUT_MS / 1000 };
