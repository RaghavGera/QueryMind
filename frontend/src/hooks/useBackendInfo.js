import { useCallback, useEffect, useState } from "react";
import { getSchema } from "../services/schemaApi";

/**
 * Live backend info for the app chrome: { status: "checking" | "connected" |
 * "unreachable", schema, error, retry }. Uses /schema (not /health, which
 * some ad blockers block).
 */
export function useBackendInfo(workspaceId = "demo") {
  // Tagged with the workspace it belongs to; another workspace's result reads as "checking".
  const [state, setState] = useState({ workspaceId: null, status: "checking", schema: null, error: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    getSchema({ refresh: attempt > 0, workspaceId })
      .then((schema) => active && setState({ workspaceId, status: "connected", schema, error: null }))
      .catch((error) => active && setState({ workspaceId, status: "unreachable", schema: null, error: error.message }));
    return () => {
      active = false;
    };
  }, [attempt, workspaceId]);

  const retry = useCallback(() => {
    setState({ workspaceId: null, status: "checking", schema: null, error: null });
    setAttempt((n) => n + 1);
  }, []);

  const current = state.workspaceId === workspaceId ? state : { status: "checking", schema: null, error: null };
  return { status: current.status, schema: current.schema, error: current.error, retry };
}
