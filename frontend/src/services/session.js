// The signed-in session and today's usage, shared by the whole app.
// Plain JS stores (subscribe/get) so React components and the API client
// can both use them; tested with node --test.

const KEY = "querymind.session";

function readStored() {
  try {
    const session = JSON.parse(globalThis.localStorage?.getItem(KEY) || "null");
    if (session?.token && (!session.expires_at || new Date(session.expires_at) > new Date())) return session;
  } catch {
    // unreadable storage: treat as signed out
  }
  return null;
}

let session = readStored();
let usage = null;
const sessionListeners = new Set();
const usageListeners = new Set();

export function getSession() {
  return session;
}

/** Save ({ token, expires_at, user }) or clear (null) the session. */
export function setSession(next) {
  session = next;
  try {
    if (next) globalThis.localStorage?.setItem(KEY, JSON.stringify(next));
    else globalThis.localStorage?.removeItem(KEY);
  } catch {
    // storage full or blocked: keep the in-memory session for this tab
  }
  if (!next) usage = null;
  sessionListeners.forEach((fn) => fn());
  usageListeners.forEach((fn) => fn());
}

export function subscribeSession(fn) {
  sessionListeners.add(fn);
  return () => sessionListeners.delete(fn);
}

export function authHeader() {
  return session?.token ? { Authorization: `Bearer ${session.token}` } : {};
}

export function getUsage() {
  return usage;
}

export function setUsage(next) {
  usage = next ? { ...usage, ...next } : null;
  usageListeners.forEach((fn) => fn());
}

export function subscribeUsage(fn) {
  usageListeners.add(fn);
  return () => usageListeners.delete(fn);
}

/** Usage from the API's X-Usage-* response headers (null when absent). */
export function usageFromHeaders(headers) {
  const scope = headers?.get?.("X-Usage-Scope");
  if (!scope) return null;
  const limit = headers.get("X-Usage-Limit");
  return { scope, used: Number(headers.get("X-Usage-Used") || 0), limit: limit === null ? null : Number(limit) };
}

/** Questions left today, or null when unlimited/unknown. */
export function remaining(current) {
  if (!current || current.limit === null || current.limit === undefined) return null;
  return Math.max(0, current.limit - (current.used || 0));
}

/**
 * What the usage allows right now. A clarification that came with a ticket
 * can still be answered after the last question: it was already counted.
 */
export function usageGate(usage, status, clarification) {
  const outOfQuestions = remaining(usage) === 0;
  const clarifying = status === "clarifying" && Boolean(clarification);
  const freeAnswer = clarifying && Boolean(clarification.ticket);
  return {
    outOfQuestions,
    showClarification: clarifying && (!outOfQuestions || freeAnswer),
    showOutPanel: outOfQuestions && status !== "processing" && status !== "generating" && !freeAnswer,
    pendingClarification: clarifying && !freeAnswer,
  };
}
