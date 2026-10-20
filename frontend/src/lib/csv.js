// Results as a CSV file (RFC 4180) that opens cleanly in Excel and Sheets.

// A cell starting with one of these is run as a formula by spreadsheets
// ("=HYPERLINK(...)"); prefixing an apostrophe keeps it plain text.
const FORMULA_START = /^[=+\-@\t\r]/;

/** One CSV field. Numbers stay numbers; text that looks like a formula is defused. */
export function csvField(value) {
  if (value === null || value === undefined) return "";
  let text = typeof value === "object" ? JSON.stringify(value) : String(value);
  if (typeof value === "string" && FORMULA_START.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** Header row plus one line per row, CRLF line endings, with a BOM so Excel reads UTF-8. */
export function toCsv(columns, rows) {
  const lines = [columns.map(csvField).join(",")];
  for (const row of rows) lines.push(columns.map((c) => csvField(row[c])).join(","));
  return `﻿${lines.join("\r\n")}\r\n`;
}

/** A file name from the question: "Which region generated the most revenue?" -> "which-region-generated-the-most-revenue.csv". */
export function csvFilename(question) {
  const slug = String(question || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/[\s_-]+/g, "-")
    .slice(0, 60)
    .replace(/-+$/, "");
  return `${slug || "querymind-results"}.csv`;
}

/** Start a download of ``rows`` (browser only). */
export function downloadCsv(columns, rows, question) {
  const blob = new Blob([toCsv(columns, rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = csvFilename(question);
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
