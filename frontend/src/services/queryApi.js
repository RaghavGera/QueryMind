import { getSettings } from "./settings";
import { authHeader, getSession, setSession, setUsage, usageFromHeaders } from "./session.js";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path) {
  if (!API_BASE) {
    throw new Error(
      "QueryMind backend is not configured. Set VITE_API_BASE_URL in the frontend deployment.",
    );
  }

  return `${API_BASE}${path}`;
}

/** An API error that keeps the HTTP status and body (sign-in and quota prompts use them). */
export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }

  get signInRequired() {
    return Boolean(this.body?.sign_in_required);
  }

  get quotaExceeded() {
    return Boolean(this.body?.quota_exceeded);
  }
}

export async function request(path, options = {}) {
  let response;

  try {
    // FormData (file uploads) sets its own multipart Content-Type with the boundary.
    const json = !(options.body instanceof FormData);
    response = await fetch(apiUrl(path), {
      ...options,
      headers: {
        ...(json ? { "Content-Type": "application/json" } : {}),
        ...authHeader(),
        ...(options.headers || {}),
      },
    });
  } catch {
    // fetch() only throws for network failures and CORS refusals, so name both
    // ends: a page origin missing from the backend's CORS list looks identical.
    throw new Error(
      `Could not reach the QueryMind backend at ${API_BASE} from ${window.location.origin}. ` +
        "Make sure the backend is running and allows this site's address (CORS).",
    );
  }

  const usage = usageFromHeaders(response.headers);
  if (usage) setUsage(usage);

  let body = null;

  try {
    body = await response.json();
  } catch {
    // Backend returned something that wasn't JSON.
  }

  if (!response.ok) {
    if (body?.usage) setUsage(body.usage);
    // A dead session: forget it so the app shows the sign-in screen.
    if (response.status === 401 && getSession()) setSession(null);
    throw new ApiError(
      body?.error || body?.detail || `Backend request failed with HTTP ${response.status}.`,
      response.status,
      body,
    );
  }

  return body;
}

/**
 * ``ticket`` comes with a clarification question: sending the answer with it
 * doesn't count as another question.
 */
export async function submitQuestion(question, clarificationContext = "", ticket = null, workspaceId = null) {
  const settings = getSettings();
  return request("/query", {
    method: "POST",
    headers: ticket ? { "X-Clarification-Ticket": ticket } : {},
    body: JSON.stringify({
      question,
      workspace_id: workspaceId && workspaceId !== "demo" ? workspaceId : null,
      clarification_context: clarificationContext || null,
      strict: settings.askForClarification,
      allow_writes: settings.allowWrites,
      allow_full_table_write: false,
    }),
  });
}

export async function getHealth() {
  return request("/health");
}

export async function confirmWrite(confirmationToken) {
  return request("/query/confirm", {
    method: "POST",
    body: JSON.stringify({ confirmation_token: confirmationToken }),
  });
}

// Accounts --------------------------------------------------------------- //

export async function signInWithGoogle({ accessToken }) {
  const body = await request("/auth/google", { method: "POST", body: JSON.stringify({ access_token: accessToken }) });
  setSession({ token: body.token, expires_at: body.expires_at, user: body.user });
  setUsage(body.usage);
  return body;
}

export async function fetchMe() {
  const body = await request("/auth/me");
  setSession({ ...getSession(), user: body.user });
  setUsage(body.usage);
  return body;
}

export async function fetchUsage() {
  const body = await request("/auth/usage");
  setUsage(body.usage);
  return body.usage;
}

export async function signOut() {
  try {
    await request("/auth/logout", { method: "POST" });
  } finally {
    setSession(null);
  }
}

// History and saved queries in the account (see services/library.js) ------ //

export async function fetchHistory() {
  return (await request("/me/history")).entries;
}

export function addHistory(entry) {
  return request("/me/history", { method: "POST", body: JSON.stringify({ entry }) });
}

export function deleteHistory(id) {
  return request(`/me/history/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function fetchSaved() {
  return (await request("/me/saved")).entries;
}

export function saveEntry(entry) {
  return request("/me/saved", { method: "PUT", body: JSON.stringify({ entry }) });
}

export function deleteSavedEntry(id) {
  return request(`/me/saved/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/** Move this browser's entries into the account; ones it already has are skipped. */
export function importEntries({ history, saved }) {
  return request("/me/import", { method: "POST", body: JSON.stringify({ history, saved }) });
}

// Workspaces and uploads (see app/workspaces.py, app/uploads.py) ----------- //

export function fetchWorkspaces() {
  return request("/workspaces");
}

export function deleteWorkspace(id) {
  return request(`/workspaces/${encodeURIComponent(id)}`, { method: "DELETE" });
}

function uploadForm(files, fields) {
  const form = new FormData();
  for (const file of files) form.append("files", file, file.name);
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null) form.append(key, typeof value === "string" ? value : JSON.stringify(value));
  }
  return form;
}

/** What the files contain, as an editable plan; ``plan`` (the edits) is checked when given. */
export function previewUpload(files, plan = null) {
  return request("/workspaces/uploads/preview", { method: "POST", body: uploadForm(files, { plan }) });
}

/** Import the files with the preview's edits as the user's workspace. */
export function importUpload(files, { plan, name, replace }) {
  return request("/workspaces/uploads", {
    method: "POST",
    body: uploadForm(files, { plan, name: name || "", replace: replace ? "true" : "false" }),
  });
}
