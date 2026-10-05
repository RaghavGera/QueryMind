import { getSettings } from "./settings";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path) {
  if (!API_BASE) {
    throw new Error(
      "QueryMind backend is not configured. Set VITE_API_BASE_URL in the frontend deployment.",
    );
  }

  return `${API_BASE}${path}`;
}

async function request(path, options = {}) {
  let response;

  try {
    response = await fetch(apiUrl(path), {
      ...options,
      headers: {
        "Content-Type": "application/json",
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

  let body = null;

  try {
    body = await response.json();
  } catch {
    // Backend returned something that wasn't JSON.
  }

  if (!response.ok) {
    throw new Error(
      body?.error ||
        body?.detail ||
        `Backend request failed with HTTP ${response.status}.`,
    );
  }

  return body;
}

export async function submitQuestion(question, clarificationContext = "") {
  const settings = getSettings();
  return request("/query", {
    method: "POST",
    body: JSON.stringify({
      question,
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
