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
    throw new Error(
      "Could not reach the QueryMind backend. Check VITE_API_BASE_URL and make sure the backend is running.",
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
  return request("/query", {
    method: "POST",
    body: JSON.stringify({
      question,
      clarification_context: clarificationContext || null,
      strict: true,
      allow_full_table_write: false,
    }),
  });
}
