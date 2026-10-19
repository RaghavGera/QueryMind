import test from "node:test";
import assert from "node:assert/strict";
import { compactNumber, dateLabeler, dateParts, fullNumber } from "./chartFormat.js";

test("timestamps are read as written, without shifting to the viewer's timezone", () => {
  assert.deepEqual(dateParts("2025-06-01T00:00:00+05:30"), { year: 2025, month: 6, day: 1, time: "00:00", midnight: true });
  assert.equal(dateParts("2025-06-01T00:00:00-08:00").month, 6);
  assert.equal(dateParts("2025-06-01").day, 1);
  assert.equal(dateParts("Laptops"), null);
  assert.equal(dateParts(2025), null);
  assert.equal(dateParts("2025-13-01"), null);
});

test("month buckets are labelled by month", () => {
  const months = ["2025-05-01T00:00:00+05:30", "2025-06-01T00:00:00+05:30", "2026-01-01T00:00:00+05:30"];
  const label = dateLabeler(months);
  assert.deepEqual(months.map(label), ["May 2025", "Jun 2025", "Jan 2026"]);
});

test("year buckets, plain dates and timestamps get matching labels", () => {
  assert.deepEqual(["2024-01-01", "2025-01-01"].map(dateLabeler(["2024-01-01", "2025-01-01"])), ["2024", "2025"]);
  assert.deepEqual(["2025-06-03", "2025-06-04"].map(dateLabeler(["2025-06-03", "2025-06-04"])), ["3 Jun 2025", "4 Jun 2025"]);
  assert.equal(dateLabeler(["2025-06-03T14:30:00Z"])("2025-06-03T14:30:00Z"), "3 Jun 2025 14:30");
});

test("columns that aren't all dates are left alone", () => {
  assert.equal(dateLabeler(["Laptops", "Audio"]), null);
  assert.equal(dateLabeler(["2025-06-01", "n/a"]), null);
  assert.equal(dateLabeler([]), null);
});

test("axis numbers are compact and tooltips show the full value", () => {
  assert.equal(compactNumber(280000), "280K");
  assert.equal(compactNumber(1550630), "1.6M");
  assert.equal(compactNumber(70), "70");
  assert.equal(fullNumber(706939), "706,939");
  assert.equal(fullNumber(1234.5), "1,234.5");
  assert.equal(fullNumber("x"), "x");
});
