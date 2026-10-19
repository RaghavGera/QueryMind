import { useEffect, useSyncExternalStore } from "react";
import { createLibrary } from "../services/library.js";
import * as api from "../services/queryApi";
import * as history from "../services/historyApi.js";
import * as saved from "../services/savedApi.js";
import { getSession, subscribeSession } from "../services/session.js";

/** The app's one library: history and saved queries, in the browser or the account. */
export const library = createLibrary({
  api: {
    importEntries: api.importEntries,
    fetchHistory: api.fetchHistory,
    fetchSaved: api.fetchSaved,
    addHistory: api.addHistory,
    deleteHistory: api.deleteHistory,
    save: api.saveEntry,
    deleteSaved: api.deleteSavedEntry,
  },
  local: { ...history, ...saved },
  getSession,
  subscribeSession,
});

/** ``{ status, history, saved, error }``; loads the lists on first use. */
export function useLibrary() {
  useEffect(() => {
    library.ensureLoaded();
  }, []);
  return useSyncExternalStore(library.subscribe, library.getState, library.getState);
}
