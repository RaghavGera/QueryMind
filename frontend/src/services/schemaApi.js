import { schema } from "../data/mockData";

const API_BASE = import.meta.env.VITE_API_BASE_URL;

export async function getSchema() {
  if (API_BASE) {
    // Real backend integration point (Phase 1 endpoints):
    // const res = await fetch(`${API_BASE}/schema`);
    // return res.json();
  }
  await new Promise((r) => setTimeout(r, 300));
  return schema;
}
