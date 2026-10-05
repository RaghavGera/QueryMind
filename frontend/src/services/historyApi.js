import { readList, writeList } from "./storedQueries.js";

const STORAGE_KEY = "querymind.history";
const MAX_ENTRIES = 50;

// Demo entries that earlier builds showed (and then saved) as if they were
// real history. They never had results, so they are filtered out.
const DEMO_IDS = new Set(["q-1038", "q-1039", "q-1040", "q-1041", "q-1042"]);

function load() {
  return readList(STORAGE_KEY).filter((entry) => !DEMO_IDS.has(entry.id));
}

export async function getHistory() {
  return load();
}

export function getHistoryEntry(id) {
  return load().find((entry) => entry.id === id) || null;
}

export async function addHistoryEntry(entry) {
  return writeList(STORAGE_KEY, [entry, ...load()].slice(0, MAX_ENTRIES));
}

export async function deleteHistoryEntry(id) {
  return writeList(STORAGE_KEY, load().filter((entry) => entry.id !== id));
}
