// Run with `npm test`. The library with a fake API, browser storage and session.
import { beforeEach, test } from "node:test";
import assert from "node:assert/strict";

class FakeStorage {
  constructor() {
    this.data = new Map();
  }
  getItem(key) {
    return this.data.has(key) ? this.data.get(key) : null;
  }
  setItem(key, value) {
    this.data.set(key, String(value));
  }
  removeItem(key) {
    this.data.delete(key);
  }
}
globalThis.localStorage = new FakeStorage();

const { createLibrary } = await import("./library.js");
const history = await import("./historyApi.js");
const saved = await import("./savedApi.js");

/** A fake /me/* API; ``failNext`` makes the next call reject like a network error. */
function fakeApi() {
  const account = { history: [], saved: [] };
  const calls = [];
  let failNext = false;
  const call = (name, fn) => async (...args) => {
    calls.push(name);
    if (failNext) {
      failNext = false;
      throw new Error(`${name} failed`);
    }
    return fn(...args);
  };
  return {
    account,
    calls,
    failNext: () => (failNext = true),
    api: {
      importEntries: call("import", async ({ history: h, saved: s }) => {
        account.history = [...h, ...account.history];
        account.saved = [...s, ...account.saved];
      }),
      fetchHistory: call("fetchHistory", async () => [...account.history]),
      fetchSaved: call("fetchSaved", async () => [...account.saved]),
      addHistory: call("addHistory", async (e) => account.history.unshift(e)),
      deleteHistory: call("deleteHistory", async (id) => (account.history = account.history.filter((e) => e.id !== id))),
      save: call("save", async (e) => account.saved.unshift(e)),
      deleteSaved: call("deleteSaved", async (id) => (account.saved = account.saved.filter((e) => e.id !== id))),
    },
  };
}

function fakeSession() {
  let session = null;
  const listeners = new Set();
  return {
    getSession: () => session,
    subscribeSession: (fn) => (listeners.add(fn), () => listeners.delete(fn)),
    signIn: (id) => {
      session = { token: "t", user: { id } };
      listeners.forEach((fn) => fn());
    },
    signOut: () => {
      session = null;
      listeners.forEach((fn) => fn());
    },
  };
}

function setup() {
  const remote = fakeApi();
  const auth = fakeSession();
  const lib = createLibrary({ api: remote.api, local: { ...history, ...saved }, ...auth });
  return { lib, remote, auth };
}

const entry = (id, question = `Question ${id}`) => ({ id, question, resolved: null, snapshot: null });

beforeEach(() => {
  globalThis.localStorage = new FakeStorage();
});

test("signed out, history and saved queries stay in this browser", async () => {
  const { lib, remote } = setup();
  await lib.addHistory(entry("q-1"));
  await lib.save({ question: "Top products", resolved: null, snapshot: null });
  assert.deepEqual(lib.getState().history.map((e) => e.id), ["q-1"]);
  assert.equal(lib.getState().saved.length, 1);
  assert.equal((await history.getHistory()).length, 1, "written to localStorage");
  assert.deepEqual(remote.calls, [], "the server is never called");
});

test("signing in moves the browser's entries into the account, then clears the browser", async () => {
  const { lib, remote, auth } = setup();
  await lib.addHistory(entry("q-1"));
  await lib.save({ question: "Top products", resolved: null, snapshot: null });
  auth.signIn(7);
  await lib.ensureLoaded();
  assert.deepEqual(remote.calls.slice(0, 1), ["import"]);
  assert.deepEqual(lib.getState().history.map((e) => e.id), ["q-1"]);
  assert.equal(lib.getState().saved[0].question, "Top products");
  assert.equal((await history.getHistory()).length, 0);
  assert.equal(saved.getSaved().length, 0);
});

test("a failed import keeps the browser's entries for next time", async () => {
  const { lib, remote, auth } = setup();
  await lib.addHistory(entry("q-1"));
  remote.failNext();
  auth.signIn(7);
  await lib.ensureLoaded();
  assert.equal(lib.getState().status, "ready", "the account's own lists still load");
  assert.equal((await history.getHistory()).length, 1);
});

test("signed in, changes go to the account; a failed change is put back", async () => {
  const { lib, remote, auth } = setup();
  auth.signIn(7);
  await lib.addHistory(entry("q-1"));
  await lib.addHistory(entry("q-2"));
  assert.deepEqual(remote.account.history.map((e) => e.id), ["q-2", "q-1"]);
  assert.deepEqual(lib.getState().history.map((e) => e.id), ["q-2", "q-1"]);

  remote.failNext();
  await assert.rejects(lib.removeHistory("q-2"), /deleteHistory failed/);
  assert.deepEqual(lib.getState().history.map((e) => e.id), ["q-2", "q-1"], "the list is restored");
  assert.equal(lib.findHistory("q-2").question, "Question q-2");
});

test("saving the same question and clarification again replaces it", async () => {
  const { lib, auth } = setup();
  auth.signIn(7);
  const first = await lib.save({ question: "Top products", resolved: null, snapshot: null });
  const second = await lib.save({ question: "Top products", resolved: null, snapshot: null });
  await lib.save({ question: "Top products", resolved: "by revenue", snapshot: null });
  assert.notEqual(first.id, second.id);
  assert.equal(lib.getState().saved.length, 2);
  assert.equal(lib.findSavedQuery({ question: "Top products", resolved: null }).id, second.id);
  await lib.removeSaved(second.id);
  assert.equal(lib.findSavedQuery({ question: "Top products", resolved: null }), null);
});

test("signing out shows this browser's (empty) lists, not the account's", async () => {
  const { lib, auth } = setup();
  auth.signIn(7);
  await lib.addHistory(entry("q-1"));
  auth.signOut();
  await lib.ensureLoaded();
  assert.deepEqual(lib.getState().history, []);
  assert.equal(lib.getState().saved.length, 0);
});

test("a failed load reports an error, and the next load tries again", async () => {
  const { lib, remote, auth } = setup();
  auth.signIn(7);
  remote.failNext(); // nothing to import, so this fails fetchHistory
  await lib.ensureLoaded();
  assert.equal(lib.getState().status, "error");
  await lib.ensureLoaded();
  assert.equal(lib.getState().status, "ready");
});
