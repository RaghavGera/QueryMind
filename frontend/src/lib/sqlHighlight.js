const KEYWORDS = [
  "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER", "ON",
  "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET", "AND", "OR", "AS",
  "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE", "DISTINCT", "IN",
  "BETWEEN", "IS", "NULL", "NOT", "LIKE", "COUNT", "SUM", "AVG", "MIN", "MAX",
];

const KEYWORD_RE = new RegExp(`\\b(${KEYWORDS.join("|")})\\b`, "gi");
const STRING_RE = /'[^']*'/g;
const NUMBER_RE = /\b\d+(\.\d+)?\b/g;
const FUNC_RE = /\b([a-zA-Z_][a-zA-Z0-9_]*)(?=\()/g;

/**
 * Tokenize a single line of SQL into { text, cls } segments for rendering.
 * Deliberately simple (regex-based) rather than a full parser/lib.
 */
export function highlightSqlLine(line) {
  const tokens = [];
  let cursor = 0;

  const matches = [];
  for (const re of [STRING_RE, KEYWORD_RE, NUMBER_RE, FUNC_RE]) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(line))) {
      matches.push({ start: m.index, end: m.index + m[0].length, text: m[0], re });
    }
  }
  matches.sort((a, b) => a.start - b.start || b.end - a.end);

  const accepted = [];
  let lastEnd = -1;
  for (const m of matches) {
    if (m.start >= lastEnd) {
      accepted.push(m);
      lastEnd = m.end;
    }
  }

  for (const m of accepted) {
    if (m.start > cursor) tokens.push({ text: line.slice(cursor, m.start), cls: "text-ink" });
    let cls = "text-ink";
    if (m.re === STRING_RE) cls = "text-accent-cyan";
    else if (m.re === KEYWORD_RE) cls = "text-accent-violet font-medium";
    else if (m.re === NUMBER_RE) cls = "text-state-warning";
    else if (m.re === FUNC_RE) cls = "text-accent-glow";
    tokens.push({ text: m.text, cls });
    cursor = m.end;
  }
  if (cursor < line.length) tokens.push({ text: line.slice(cursor), cls: "text-ink" });

  return tokens.length ? tokens : [{ text: line, cls: "text-ink" }];
}
