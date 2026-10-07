// Static copy used by the UI. Nothing here pretends to be live data.

export const suggestedQuestions = [
  "How many new customers signed up last month?",
  "What were our top 10 products?",
  "Which region generated the most revenue?",
  "Show customers whose spending increased this quarter.",
];

// Labels for the pipeline beam while a question is being answered. They
// describe the pipeline; they are not live progress reports.
export const pipelineStagesInitial = [
  "Understanding request",
  "Mapping to your schema",
  "Checking for ambiguity",
];

export const pipelineStagesAfterClarification = [
  "Intent resolved",
  "Generating SQL",
  "Validating query",
  "Executing",
];

export const architectureSteps = [
  { key: "question", label: "User Question", detail: "The raw natural-language question, exactly as typed." },
  { key: "intent", label: "Intent Extractor", detail: "An LLM (Gemini, with Groq as a fallback) maps the question onto tables, columns, filters and aggregations." },
  { key: "ambiguity", label: "Ambiguity Engine", detail: "Checks the intent against the live schema for missing filters, unclear joins and vague terms like “top” or “expensive”." },
  { key: "clarification", label: "Clarification", detail: "If something is genuinely unclear, QueryMind asks instead of guessing." },
  { key: "resolved", label: "Resolved Intent", detail: "The intent, now unambiguous, with your answer folded back in." },
  { key: "planner", label: "Query Planner", detail: "Decides the base table, the join path from your foreign keys, and the clause structure." },
  { key: "generator", label: "SQL Generator", detail: "Builds parameterized SQL with quoted identifiers. Values are never pasted into the query text." },
  { key: "validator", label: "SQL Validator", detail: "A hard-coded safety net blocks updates without a WHERE clause and refuses DELETE." },
  { key: "database", label: "Database", detail: "SELECT queries run directly. Inserts and updates are off by default and run only after you confirm a preview." },
  { key: "result", label: "Results", detail: "Rows come back as a table, with a chart when the shape fits, alongside the exact SQL that produced them." },
];
