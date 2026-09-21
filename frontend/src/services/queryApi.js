import { clarificationOptions, demoResults, demoSql } from "../data/mockData";

// Set VITE_API_BASE_URL to point this at the real QueryMind backend
// (see app/main.py's POST /query). Until then, everything below runs
// against realistic mock data so the UI is fully interactive standalone.
const API_BASE = import.meta.env.VITE_API_BASE_URL;

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function looksAmbiguous(question) {
  return /\bbest\b/i.test(question) && !/spending|orders|average/i.test(question);
}

function pickResultSet(question) {
  if (/sign[\s-]?up|new customers?/i.test(question)) return "signups";
  if (/\bproducts?\b/i.test(question)) return "products";
  if (/\bregion(s)?\b|\bcountr(y|ies)\b/i.test(question)) return "region";
  if (/\brevenue\b|\bsales\b/i.test(question)) return "revenue";
  if (/\border(s|ed)?\b/i.test(question)) return "orders";
  if (/\baverage\b|\baov\b/i.test(question)) return "aov";
  return "spending";
}

/**
 * Submit a natural language question. Returns either a clarification
 * request or a resolved intent ready for SQL generation.
 */
export async function submitQuestion(question) {
  if (API_BASE) {
    // Real backend integration point:
    // const res = await fetch(`${API_BASE}/query`, {
    //   method: "POST",
    //   headers: { "Content-Type": "application/json" },
    //   body: JSON.stringify({ question }),
    // });
    // return res.json();
  }

  await delay(900);

  if (looksAmbiguous(question)) {
    return {
      status: "needs_clarification",
      clarification: {
        question: 'How should "best customers" be measured?',
        options: clarificationOptions,
      },
    };
  }

  return { status: "resolved", resultKey: pickResultSet(question) };
}

/**
 * Resolve a clarification choice and continue the pipeline through to a result.
 */
export async function resolveClarification(choiceId) {
  await delay(700);
  return runGeneration(choiceId);
}

/**
 * Run generation + (simulated) execution for an already-resolved intent.
 */
export async function runGeneration(resultKey) {
  await delay(1100);

  const key = demoSql[resultKey] ? resultKey : "spending";
  const rows = demoResults[key] ?? demoResults.spending;
  const columns = Object.keys(rows[0] ?? {});

  return {
    status: "success",
    sql: demoSql[key] ?? demoSql.spending,
    result: {
      columns,
      rows,
    },
    executionMs: Math.round(120 + Math.random() * 140),
    dialect: "PostgreSQL",
  };
}
