// Run with `npm test` (node --test; no extra dependencies).
import { beforeEach, test } from "node:test";
import assert from "node:assert/strict";

/** In-memory localStorage that refuses writes past ``limit`` characters. */
class FakeStorage {
  constructor(limit = Infinity) {
    this.limit = limit;
    this.data = new Map();
  }
  getItem(key) {
    return this.data.has(key) ? this.data.get(key) : null;
  }
  setItem(key, value) {
    if (String(value).length > this.limit) throw new Error("QuotaExceededError");
    this.data.set(key, String(value));
  }
  removeItem(key) {
    this.data.delete(key);
  }
}

globalThis.localStorage = new FakeStorage();

const { MAX_SNAPSHOT_ROWS, makeSnapshot, newId, readList, sameQuery, writeList } = await import("./storedQueries.js");
const history = await import("./historyApi.js");
const saved = await import("./savedApi.js");

const rows = (n) => Array.from({ length: n }, (_, i) => ({ id: i, name: `row ${i}` }));
const result = (n) => ({ columns: ["id", "name"], rows: rows(n) });

beforeEach(() => {
  globalThis.localStorage = new FakeStorage();
});

test("snapshot keeps the SQL and caps rows but remembers the real total", () => {
  const snap = makeSnapshot({ sql: "SELECT 1", params: ["India"], result: result(500), warnings: ["w"] });
  assert.equal(snap.sql, "SELECT 1");
  assert.deepEqual(snap.params, ["India"]);
  assert.deepEqual(snap.columns, ["id", "name"]);
  assert.equal(snap.rows.length, MAX_SNAPSHOT_ROWS);
  assert.equal(snap.totalRows, 500);
  assert.deepEqual(snap.warnings, ["w"]);
});

test("ids are unique within the same millisecond", () => {
  const ids = new Set(Array.from({ length: 1000 }, () => newId("s")));
  assert.equal(ids.size, 1000);
});

test("same question with a different clarification is a different query", () => {
  assert.ok(sameQuery({ question: "q", resolved: null }, { question: "q" }));
  assert.ok(!sameQuery({ question: "q", resolved: "by revenue" }, { question: "q", resolved: null }));
});

test("readList survives missing or corrupt storage", () => {
  assert.deepEqual(readList("nothing"), []);
  localStorage.setItem("bad", "{not json");
  assert.deepEqual(readList("bad"), []);
  localStorage.setItem("object", "{}");
  assert.deepEqual(readList("object"), []);
});

test("when storage is full, the oldest snapshots are dropped but entries kept", () => {
  const entries = [0, 1, 2].map((i) => ({
    id: `q-${i}`,
    question: `question ${i}`,
    snapshot: makeSnapshot({ sql: "SELECT", result: result(50) }),
  }));
  const oneSnapshot = JSON.stringify(entries[0]).length;
  globalThis.localStorage = new FakeStorage(oneSnapshot * 2); // room for ~1.5 entries

  const kept = writeList("k", entries);

  assert.equal(kept.length, 3);
  assert.ok(kept[0].snapshot, "newest result is kept");
  assert.equal(kept[2].snapshot, null, "oldest result is dropped first");
  assert.deepEqual(readList("k"), kept);
});

test("history: newest first, reopenable by id, deletable", async () => {
  await history.addHistoryEntry({ id: "q-1", question: "first", snapshot: makeSnapshot({ sql: "S1", result: result(3) }) });
  await history.addHistoryEntry({ id: "q-2", question: "second", snapshot: null });

  assert.deepEqual((await history.getHistory()).map((e) => e.id), ["q-2", "q-1"]);
  assert.equal(history.getHistoryEntry("q-1").snapshot.sql, "S1");
  assert.equal(history.getHistoryEntry("missing"), null);

  await history.deleteHistoryEntry("q-1");
  assert.deepEqual((await history.getHistory()).map((e) => e.id), ["q-2"]);
});

test("history hides the fake demo entries older builds wrote to storage", async () => {
  localStorage.setItem(
    "querymind.history",
    JSON.stringify([{ id: "q-1777", question: "real" }, { id: "q-1042", question: "Show me last month's best customers" }]),
  );
  assert.deepEqual((await history.getHistory()).map((e) => e.id), ["q-1777"]);
});

test("history keeps at most 50 entries", async () => {
  for (let i = 0; i < 55; i += 1) await history.addHistoryEntry({ id: `q-${i}`, question: `${i}` });
  const list = await history.getHistory();
  assert.equal(list.length, 50);
  assert.equal(list[0].id, "q-54");
});

test("saved: save, find, re-save replaces, remove", () => {
  const snapshot = makeSnapshot({ sql: "S", result: result(2) });
  const first = saved.saveQuery({ question: "Top products", resolved: null, snapshot });

  assert.equal(saved.findSaved({ question: "Top products", resolved: null }).id, first.id);
  assert.equal(saved.findSaved({ question: "Top products", resolved: "by revenue" }), null);
  assert.equal(saved.getSavedEntry(first.id).snapshot.sql, "S");
  assert.ok(first.savedAt);

  saved.saveQuery({ question: "Top products", resolved: null, snapshot });
  assert.equal(saved.getSaved().length, 1, "saving the same query again does not duplicate it");

  saved.saveQuery({ question: "Top products", resolved: "by revenue", snapshot });
  assert.equal(saved.getSaved().length, 2);

  saved.deleteSaved(saved.getSaved()[0].id);
  assert.equal(saved.getSaved().length, 1);
});
