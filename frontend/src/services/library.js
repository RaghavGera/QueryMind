/*
 * Query history and saved queries, wherever they live.
 *
 *   Signed out: this browser (historyApi / savedApi, localStorage).
 *   Signed in:  the account (/me/*). On sign-in the browser's entries are
 *               moved into the account, then cleared from the browser.
 *
 * The lists are kept in memory so the UI can read them synchronously; every
 * change updates them at once and is then stored. A failed store puts the
 * list back and rethrows, so the caller can say so.
 *
 * ``createLibrary`` takes its dependencies so it can be tested without a
 * browser or a server; hooks/useLibrary.js wires the real ones.
 */
import { newId, sameQuery } from "./storedQueries.js";

export const HISTORY_LIMIT = 50;

export function createLibrary({ api, local, getSession, subscribeSession }) {
  let state = { key: null, status: "idle", history: [], saved: [], error: null };
  let pending = null;
  const listeners = new Set();

  const set = (patch) => {
    state = { ...state, ...patch };
    listeners.forEach((fn) => fn());
  };

  const currentKey = () => {
    const session = getSession();
    return session?.user?.id != null ? `user:${session.user.id}` : "local";
  };

  async function fetchLists(key) {
    if (key === "local") {
      return { history: await local.getHistory(), saved: local.getSaved() };
    }
    const browserHistory = await local.getHistory();
    const browserSaved = local.getSaved();
    if (browserHistory.length || browserSaved.length) {
      try {
        await api.importEntries({ history: browserHistory, saved: browserSaved });
        local.clearHistory();
        local.clearSaved();
      } catch {
        // Keep them in the browser and try again next time; the account's
        // own lists still load below.
      }
    }
    const [history, saved] = await Promise.all([api.fetchHistory(), api.fetchSaved()]);
    return { history, saved };
  }

  /** Load the lists for whoever is signed in now (once per sign-in). */
  function ensureLoaded() {
    const key = currentKey();
    if (state.key === key && pending && state.status !== "error") return pending;
    set({ key, status: "loading", history: [], saved: [], error: null });
    pending = fetchLists(key).then(
      (lists) => {
        if (state.key === key) set({ ...lists, status: "ready" });
      },
      (error) => {
        if (state.key === key) set({ status: "error", error: error?.message || "Could not load your queries." });
      },
    );
    return pending;
  }

  subscribeSession(() => {
    if (state.key !== null && state.key !== currentKey()) ensureLoaded();
  });

  /** Update the list now; store it; on failure put it back and rethrow. */
  async function change(listName, next, store) {
    const before = state[listName];
    set({ [listName]: next });
    try {
      await store();
    } catch (error) {
      set({ [listName]: before });
      throw error;
    }
  }

  return {
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    getState: () => state,
    ensureLoaded,

    findHistory: (id) => state.history.find((entry) => entry.id === id) || null,
    findSaved: (id) => state.saved.find((entry) => entry.id === id) || null,
    findSavedQuery: (query) => state.saved.find((entry) => sameQuery(entry, query)) || null,

    async addHistory(entry) {
      await ensureLoaded();
      if (state.key === "local") return set({ history: await local.addHistoryEntry(entry) });
      const next = [entry, ...state.history.filter((e) => e.id !== entry.id)].slice(0, HISTORY_LIMIT);
      return change("history", next, () => api.addHistory(entry));
    },

    async removeHistory(id) {
      await ensureLoaded();
      if (state.key === "local") return set({ history: await local.deleteHistoryEntry(id) });
      return change("history", state.history.filter((e) => e.id !== id), () => api.deleteHistory(id));
    },

    /** Save (or refresh) a query; the same question + clarification replaces the old entry. */
    async save(entry) {
      await ensureLoaded();
      if (state.key === "local") {
        const saved = local.saveQuery(entry);
        set({ saved: local.getSaved() });
        return saved;
      }
      const saved = { ...entry, id: newId("s"), savedAt: new Date().toISOString() };
      await change("saved", [saved, ...state.saved.filter((e) => !sameQuery(e, saved))], () => api.save(saved));
      return saved;
    },

    async removeSaved(id) {
      await ensureLoaded();
      if (state.key === "local") return set({ saved: local.deleteSaved(id) });
      return change("saved", state.saved.filter((e) => e.id !== id), () => api.deleteSaved(id));
    },
  };
}
