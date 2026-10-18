import { test } from "node:test";
import assert from "node:assert/strict";
import { humanizeColumn, inlineParams, sqlLiteral } from "./sqlDisplay.js";

test("parameters are inlined in order as SQL literals", () => {
  const sql = 'WHERE "orders"."order_date" BETWEEN %s AND %s';
  assert.equal(inlineParams(sql, ["2026-09-01", "2026-09-30"]), "WHERE \"orders\".\"order_date\" BETWEEN '2026-09-01' AND '2026-09-30'");
  assert.equal(inlineParams("LIMIT %s", [10]), "LIMIT 10");
  assert.equal(inlineParams("x = %s", [null]), "x = NULL");
});

test("quotes are escaped and %% stays a literal percent", () => {
  assert.equal(sqlLiteral("O'Brien"), "'O''Brien'");
  assert.equal(inlineParams("name ILIKE %s AND note LIKE '100%%'", ["%lap%"]), "name ILIKE '%lap%' AND note LIKE '100%'");
});

test("missing values leave the placeholder visible instead of guessing", () => {
  assert.equal(inlineParams("a = %s AND b = %s", [1]), "a = 1 AND b = %s");
  assert.equal(inlineParams(null, []), null);
});

test("column names read as headings", () => {
  assert.equal(humanizeColumn("sum_quantity_x_unit_price"), "Sum quantity × unit price");
  assert.equal(humanizeColumn("count_order_id"), "Count order id");
  assert.equal(humanizeColumn("country"), "Country");
  assert.equal(humanizeColumn("avg_price_per_unit"), "Avg price / unit");
});
