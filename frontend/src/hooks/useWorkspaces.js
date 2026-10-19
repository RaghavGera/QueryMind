import { useEffect, useSyncExternalStore } from "react";
import { createWorkspaceStore } from "../services/workspaces.js";
import { deleteWorkspace, fetchWorkspaces } from "../services/queryApi";
import { getSession, subscribeSession } from "../services/session.js";

/** The app's one workspace store (see services/workspaces.js). */
export const workspaces = createWorkspaceStore({
  api: { fetchWorkspaces, deleteWorkspace },
  getSession,
  subscribeSession,
  storage: localStorage,
});

/** ``{ status, list, activeId, canCreate, notice, error }``; loads on first use. */
export function useWorkspaces() {
  useEffect(() => {
    workspaces.ensureLoaded();
  }, []);
  return useSyncExternalStore(workspaces.subscribe, workspaces.getState, workspaces.getState);
}
