import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";

class FakeStorage {
  constructor() { this.data = new Map(); }
  getItem(k) { return this.data.has(k) ? this.data.get(k) : null; }
  setItem(k, v) { this.data.set(k, String(v)); }
  removeItem(k) { this.data.delete(k); }
}
globalThis.localStorage = new FakeStorage();
const s = await import("./session.js");

beforeEach(() => s.setSession(null));

test("a session is stored, sent as a Bearer header, and cleared", () => {
  assert.deepEqual(s.authHeader(), {});
  s.setSession({ token: "abc", expires_at: new Date(Date.now() + 60_000).toISOString(), user: { email: "a@b" } });
  assert.deepEqual(s.authHeader(), { Authorization: "Bearer abc" });
  assert.ok(globalThis.localStorage.getItem("querymind.session").includes("abc"));
  s.setSession(null);
  assert.deepEqual(s.authHeader(), {});
  assert.equal(globalThis.localStorage.getItem("querymind.session"), null);
});

test("listeners hear session changes, and signing out clears usage", () => {
  let calls = 0;
  const stop = s.subscribeSession(() => (calls += 1));
  s.setUsage({ scope: "user", used: 3, limit: 20 });
  s.setSession({ token: "x" });
  s.setSession(null);
  stop();
  assert.equal(calls, 2);
  assert.equal(s.getUsage(), null);
});

test("usage is read from the X-Usage-* headers", () => {
  const headers = new Map([["X-Usage-Scope", "anonymous"], ["X-Usage-Used", "2"], ["X-Usage-Limit", "3"]]);
  assert.deepEqual(s.usageFromHeaders({ get: (k) => headers.get(k) ?? null }), { scope: "anonymous", used: 2, limit: 3 });
  assert.equal(s.usageFromHeaders({ get: () => null }), null);
});

test("remaining questions never go negative and unlimited is null", () => {
  assert.equal(s.remaining({ used: 2, limit: 3 }), 1);
  assert.equal(s.remaining({ used: 5, limit: 3 }), 0);
  assert.equal(s.remaining({ used: 5, limit: null }), null);
  assert.equal(s.remaining(null), null);
});

test("a ticketed clarification can still be answered after the last free question", () => {
  const out = { used: 3, limit: 3 };
  const ticketed = s.usageGate(out, "clarifying", { question: "Ranked by what?", ticket: "t" });
  assert.deepEqual(ticketed, { outOfQuestions: true, showClarification: true, showOutPanel: false, pendingClarification: false });
  const unticketed = s.usageGate(out, "clarifying", { question: "Ranked by what?", ticket: null });
  assert.equal(unticketed.showClarification, false);
  assert.equal(unticketed.showOutPanel && unticketed.pendingClarification, true);
  assert.equal(s.usageGate(out, "processing", null).showOutPanel, false, "not while a question is running");
  assert.equal(s.usageGate({ used: 1, limit: 3 }, "clarifying", { ticket: null }).showClarification, true);
});
