// Run with `npm test`. The workspace store with a fake API, session and storage.
import { test } from "node:test";
import assert from "node:assert/strict";
import { DEMO_ID, createWorkspaceStore, entryWorkspace, expiresIn } from "./workspaces.js";

class FakeStorage {
  constructor() {
    this.data = new Map();
  }
  getItem(k) {
    return this.data.has(k) ? this.data.get(k) : null;
  }
  setItem(k, v) {
    this.data.set(k, String(v));
  }
}

const DEMO = { id: "demo", kind: "demo", name: "Demo store" };
const OWN = { id: "42", kind: "upload", name: "HR data", expires_at: "2026-10-27T00:00:00Z" };

function setup({ list = [DEMO, OWN], token = "t", stored = null } = {}) {
  const storage = new FakeStorage();
  if (stored) storage.setItem("querymind.workspace", stored);
  let session = token ? { token } : null;
  const listeners = new Set();
  const server = { list, deleted: [] };
  const store = createWorkspaceStore({
    api: {
      fetchWorkspaces: async () => ({ workspaces: server.list, can_create: Boolean(session) }),
      deleteWorkspace: async (id) => {
        server.deleted.push(id);
        server.list = server.list.filter((w) => w.id !== id);
      },
    },
    getSession: () => session,
    subscribeSession: (fn) => listeners.add(fn),
    storage,
  });
  const signOut = () => {
    session = null;
    server.list = [DEMO];
    listeners.forEach((fn) => fn());
  };
  return { store, storage, server, signOut };
}

test("the demo is active until the user picks their own workspace, and the choice is remembered", async () => {
  const { store, storage } = setup();
  await store.ensureLoaded();
  assert.equal(store.getState().activeId, DEMO_ID);
  assert.equal(store.own().name, "HR data");
  store.setActive("42");
  assert.equal(store.active().name, "HR data");
  assert.equal(storage.getItem("querymind.workspace"), "42");
});

test("an expired workspace falls back to the demo with a notice", async () => {
  const { store } = setup({ list: [DEMO], stored: "42" });
  await store.ensureLoaded();
  assert.equal(store.getState().activeId, DEMO_ID);
  assert.match(store.getState().notice, /expired or was removed/);
});

test("signing out goes back to the demo", async () => {
  const { store, signOut } = setup({ stored: "42" });
  await store.ensureLoaded();
  assert.equal(store.getState().activeId, "42");
  signOut();
  await store.ensureLoaded();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(store.getState().activeId, DEMO_ID);
  assert.equal(store.getState().notice, null, "signing out is not an expiry");
});

test("deleting the active workspace switches to the demo", async () => {
  const { store, server } = setup({ stored: "42" });
  await store.ensureLoaded();
  await store.remove("42");
  assert.deepEqual(server.deleted, ["42"]);
  assert.equal(store.getState().activeId, DEMO_ID);
  assert.equal(store.own(), null);
});

test("a new import becomes the active workspace", async () => {
  const { store, server } = setup({ list: [DEMO] });
  await store.ensureLoaded();
  server.list = [DEMO, OWN];
  await store.useNew(OWN);
  assert.equal(store.getState().activeId, "42");
});

test("expiry labels and which workspace an entry belongs to", () => {
  const now = Date.parse("2026-10-20T00:00:00Z");
  assert.equal(expiresIn("2026-10-27T00:00:00Z", now), "expires in 7 days");
  assert.equal(expiresIn("2026-10-20T05:00:00Z", now), "expires in 5 hours");
  assert.equal(expiresIn("2026-10-20T00:30:00Z", now), "expires soon");
  assert.equal(expiresIn("2026-10-19T00:00:00Z", now), "expired");
  assert.equal(expiresIn(null), null);
  assert.equal(entryWorkspace({ question: "old entry" }), DEMO_ID);
  assert.equal(entryWorkspace({ workspaceId: "42" }), "42");
});

test("history follows the active workspace and keeps entries of expired ones apart", async () => {
  const { splitByWorkspace } = await import("./workspaces.js");
  const entries = [
    { id: "a", question: "old, before workspaces" },
    { id: "b", workspaceId: "42" },
    { id: "c", workspaceId: "7" }, // a workspace that expired
    { id: "d", workspaceId: "demo" },
  ];
  const known = (id) => ["demo", "42"].includes(id);
  assert.deepEqual(
    splitByWorkspace(entries, "demo", known),
    { current: [entries[0], entries[3]], expired: [entries[2]], elsewhere: 1 },
  );
  assert.deepEqual(splitByWorkspace(entries, "42", known).current.map((e) => e.id), ["b"]);
});
