/*
 * Which data questions go to: the demo store, or the signed-in user's own
 * workspace (one per user; see app/workspaces.py). The active choice is kept
 * in this browser. If it disappears (expired, deleted, or signed out) the demo
 * becomes active again and ``notice`` says why.
 *
 * ``createWorkspaceStore`` takes its dependencies so it can be tested without
 * a browser or a server; hooks/useWorkspaces.js wires the real ones.
 */

export const DEMO_ID = "demo";
const ACTIVE_KEY = "querymind.workspace";
const DEMO = { id: DEMO_ID, kind: "demo", name: "Demo store", read_only: true, expires_at: null };

export function createWorkspaceStore({ api, getSession, subscribeSession, storage }) {
  const read = () => {
    try {
      return storage.getItem(ACTIVE_KEY) || DEMO_ID;
    } catch {
      return DEMO_ID;
    }
  };
  let state = { status: "idle", list: [DEMO], activeId: read(), canCreate: false, notice: null, error: null };
  let pending = null;
  const listeners = new Set();

  const set = (patch) => {
    state = { ...state, ...patch };
    if ("activeId" in patch) {
      try {
        storage.setItem(ACTIVE_KEY, state.activeId);
      } catch {
        // storage full or blocked: the choice lasts until reload
      }
    }
    listeners.forEach((fn) => fn());
  };

  function load() {
    set({ status: state.status === "ready" ? "ready" : "loading", error: null });
    pending = api.fetchWorkspaces().then(
      (body) => {
        const list = body.workspaces?.length ? body.workspaces : [DEMO];
        const known = list.some((w) => w.id === state.activeId);
        set({
          status: "ready",
          list,
          canCreate: Boolean(body.can_create),
          activeId: known ? state.activeId : DEMO_ID,
          notice: known || state.activeId === DEMO_ID ? state.notice : "Your workspace has expired or was removed, so you're on the demo store again.",
        });
      },
      (error) => set({ status: "error", error: error?.message || "Could not load your workspaces." }),
    );
    return pending;
  }

  let lastSession = getSession()?.token || null;
  subscribeSession(() => {
    const token = getSession()?.token || null;
    if (token === lastSession) return;
    lastSession = token;
    if (!token && state.activeId !== DEMO_ID) set({ activeId: DEMO_ID, notice: null });
    load();
  });

  return {
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    getState: () => state,
    /** Load once; later calls reuse the result (``refresh`` reloads). */
    ensureLoaded: () => pending || load(),
    refresh: load,
    active: () => state.list.find((w) => w.id === state.activeId) || DEMO,
    own: () => state.list.find((w) => w.id !== DEMO_ID) || null,
    isKnown: (id) => !id || id === DEMO_ID || state.list.some((w) => w.id === id),
    setActive(id) {
      set({ activeId: state.list.some((w) => w.id === id) ? id : DEMO_ID, notice: null });
    },
    dismissNotice: () => set({ notice: null }),
    /** After an import: reload and switch to the new workspace. */
    async useNew(workspace) {
      await load();
      set({ activeId: state.list.some((w) => w.id === workspace.id) ? workspace.id : DEMO_ID, notice: null });
    },
    async remove(id) {
      await api.deleteWorkspace(id);
      if (state.activeId === id) set({ activeId: DEMO_ID });
      await load();
    },
  };
}

/** "expires in 6 days" / "expires in 3 hours" / "expires soon". */
export function expiresIn(isoDate, now = Date.now()) {
  if (!isoDate) return null;
  const ms = new Date(isoDate).getTime() - now;
  if (!(ms > 0)) return "expired";
  const hours = ms / 3_600_000;
  if (hours >= 36) return `expires in ${Math.round(hours / 24)} days`;
  if (hours >= 1.5) return `expires in ${Math.round(hours)} hours`;
  return "expires soon";
}

/** Which workspace a history or saved entry belongs to (entries before workspaces: the demo). */
export function entryWorkspace(entry) {
  return entry?.workspaceId || DEMO_ID;
}

/**
 * History/saved entries for the History and Saved pages: the active
 * workspace's, entries of workspaces that no longer exist (expired), and how
 * many belong to another workspace that still exists.
 */
export function splitByWorkspace(entries, activeId, isKnown) {
  const current = [];
  const expired = [];
  let elsewhere = 0;
  for (const entry of entries) {
    const id = entryWorkspace(entry);
    if (id === (activeId || DEMO_ID)) current.push(entry);
    else if (isKnown(id)) elsewhere += 1;
    else expired.push(entry);
  }
  return { current, expired, elsewhere };
}
