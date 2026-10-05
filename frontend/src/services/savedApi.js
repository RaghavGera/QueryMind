import { newId, readList, sameQuery, writeList } from "./storedQueries.js";

const STORAGE_KEY = "querymind.saved";

export function getSaved() {
  return readList(STORAGE_KEY);
}

export function getSavedEntry(id) {
  return getSaved().find((entry) => entry.id === id) || null;
}

/** The saved entry for this question + clarification, if any. */
export function findSaved(query) {
  return getSaved().find((entry) => sameQuery(entry, query)) || null;
}

/** Save (or refresh) a query; saving the same question again replaces it. */
export function saveQuery(entry) {
  const others = getSaved().filter((saved) => !sameQuery(saved, entry));
  const saved = { ...entry, id: newId("s"), savedAt: new Date().toISOString() };
  writeList(STORAGE_KEY, [saved, ...others]);
  return saved;
}

export function deleteSaved(id) {
  return writeList(STORAGE_KEY, getSaved().filter((entry) => entry.id !== id));
}
