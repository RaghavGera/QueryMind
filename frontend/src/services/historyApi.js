import { queryHistory } from "../data/mockData";

const STORAGE_KEY = "querymind.history";

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // fall through to seed data
  }
  return queryHistory;
}

function save(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // best-effort only
  }
}

export async function getHistory() {
  await new Promise((r) => setTimeout(r, 200));
  return load();
}

export async function addHistoryEntry(entry) {
  const list = [entry, ...load()];
  save(list);
  return list;
}

export async function deleteHistoryEntry(id) {
  const list = load().filter((h) => h.id !== id);
  save(list);
  return list;
}
