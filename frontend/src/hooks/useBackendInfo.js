import { useCallback, useEffect, useState } from "react";
import { getSchema } from "../services/schemaApi";

/**
 * Live backend info for the app chrome: { status: "checking" | "connected" |
 * "unreachable", schema, error, retry }. Uses /schema (not /health, which
 * some ad blockers block).
 */
export function useBackendInfo() {
  const [state, setState] = useState({ status: "checking", schema: null, error: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    getSchema({ refresh: attempt > 0 })
      .then((schema) => active && setState({ status: "connected", schema, error: null }))
      .catch((error) => active && setState({ status: "unreachable", schema: null, error: error.message }));
    return () => {
      active = false;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setState({ status: "checking", schema: null, error: null });
    setAttempt((n) => n + 1);
  }, []);

  return { ...state, retry };
}
