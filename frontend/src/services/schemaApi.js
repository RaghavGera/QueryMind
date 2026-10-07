import { request } from "./queryApi";
import { toSchemaView } from "./schemaShape.js";

let cached = null;

/** The live schema from GET /schema, shaped for the UI. Fetched once per page load. */
export function getSchema({ refresh = false } = {}) {
  if (!cached || refresh) {
    cached = request("/schema").then(toSchemaView);
    cached.catch(() => {
      cached = null; // let the next caller retry
    });
  }
  return cached;
}
