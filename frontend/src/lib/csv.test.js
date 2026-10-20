import test from "node:test";
import assert from "node:assert/strict";
import { csvField, csvFilename, toCsv } from "./csv.js";

test("fields are quoted only when they need it", () => {
  assert.equal(csvField("India"), "India");
  assert.equal(csvField("Smith, Ann"), '"Smith, Ann"');
  assert.equal(csvField('say "hi"'), '"say ""hi"""');
  assert.equal(csvField("two\nlines"), '"two\nlines"');
  assert.equal(csvField(706939), "706939");
  assert.equal(csvField(-5), "-5", "a negative number is a number, not a formula");
  assert.equal(csvField(null), "");
  assert.equal(csvField(undefined), "");
  assert.equal(csvField(true), "true");
});

test("text that a spreadsheet would run as a formula is defused", () => {
  for (const evil of ["=HYPERLINK(\"http://x\")", "+1+1", "-2+3", "@SUM(A1)"]) {
    assert.ok(csvField(evil).replace(/^"/, "").startsWith("'"), evil);
  }
  assert.equal(csvField("=1+1"), "'=1+1");
});

test("a table becomes CSV with a BOM and CRLF line endings", () => {
  const csv = toCsv(["country", "revenue"], [{ country: "India", revenue: 706939 }, { country: "Côte d'Ivoire", revenue: null }]);
  assert.equal(csv, "﻿country,revenue\r\nIndia,706939\r\nCôte d'Ivoire,\r\n");
});

test("the file is named after the question", () => {
  assert.equal(csvFilename("Which region generated the most revenue?"), "which-region-generated-the-most-revenue.csv");
  assert.equal(csvFilename(""), "querymind-results.csv");
  assert.equal(csvFilename("Été: sales / costs!"), "ete-sales-costs.csv");
  assert.ok(csvFilename("x".repeat(200)).length <= 64);
});
