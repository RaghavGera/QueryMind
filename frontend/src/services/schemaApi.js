import { request } from "./queryApi";
import { toSchemaView } from "./schemaShape.js";

const cached = new Map();

/** The live schema of a workspace from GET /schema, shaped for the UI. Fetched once per workspace and page load. */
export function getSchema({ refresh = false, workspaceId = "demo" } = {}) {
  const key = workspaceId || "demo";
  if (!cached.has(key) || refresh) {
    const query = key === "demo" ? "" : `?workspace_id=${encodeURIComponent(key)}`;
    const promise = request(`/schema${query}`).then(toSchemaView);
    promise.catch(() => cached.delete(key)); // let the next caller retry
    cached.set(key, promise);
  }
  return cached.get(key);
}

/** Forget a workspace's schema (after it was replaced or deleted). */
export function forgetSchema(workspaceId) {
  cached.delete(workspaceId || "demo");
}
