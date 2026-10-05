/*
 * Browser storage shared by Query History and Saved Queries.
 *
 * Each entry keeps a snapshot of its result (SQL + rows) so it can be reopened
 * without calling the backend again. localStorage holds ~5 MB, so snapshots
 * are capped at MAX_SNAPSHOT_ROWS rows, and when storage is full the oldest
 * snapshots are dropped (the entries themselves are kept).
 */

export const MAX_SNAPSHOT_ROWS = 200;

/** Unique even for two entries created in the same millisecond. */
export function newId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function makeSnapshot({ sql, params, result, warnings }) {
  const rows = result?.rows || [];
  return {
    sql: sql || null,
    params: params || [],
    columns: result?.columns || [],
    rows: rows.slice(0, MAX_SNAPSHOT_ROWS),
    totalRows: rows.length,
    warnings: warnings || [],
  };
}

/** Same question + same clarification answer = same query. */
export function sameQuery(a, b) {
  return a.question === b.question && (a.resolved || null) === (b.resolved || null);
}

export function readList(key) {
  try {
    const list = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

/**
 * Persist ``list`` (newest first). If the browser refuses because storage is
 * full, drop the oldest stored result and retry. Returns what was kept.
 */
export function writeList(key, list) {
  let current = list;
  for (;;) {
    try {
      localStorage.setItem(key, JSON.stringify(current));
      return current;
    } catch {
      const oldest = current.findLastIndex((entry) => entry.snapshot);
      if (oldest === -1) return current; // nothing left to shrink
      current = current.map((entry, i) => (i === oldest ? { ...entry, snapshot: null } : entry));
    }
  }
}
