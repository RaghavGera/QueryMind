import test from "node:test";
import assert from "node:assert/strict";
import { aggregateLabel, changesFrom, draftProblem, initialDraft, joinAdjusted, operatorLabel, sortLabel } from "./tweaks.js";

// The shapes /query returns in "tweaks" (app/tweaks.py describe).
const controls = [
  { id: "agg:0", kind: "aggregate", label: "price", type: "number", value: "MAX", options: ["MAX", "MIN", "AVG", "SUM", "COUNT"] },
  { id: "sort", kind: "sort", label: "price", type: "number", value: "desc", options: ["desc", "asc"] },
  { id: "limit", kind: "limit", label: "rows", value: 5, min: 1, max: 1000 },
  { id: "where:0", kind: "filter", label: "price", type: "number", operator: ">", operators: ["=", "!=", ">", "<", ">=", "<="], value: 100 },
  { id: "where:1", kind: "filter", label: "order date", type: "date", operator: "BETWEEN", operators: ["BETWEEN"], value: ["2025-01-01", "2025-02-01"] },
];

test("an untouched draft sends nothing", () => {
  assert.deepEqual(changesFrom(controls, initialDraft(controls)), {});
});

test("only the edited parts are sent, in the backend's shape", () => {
  const draft = initialDraft(controls);
  draft["agg:0"] = "MIN";
  draft.sort = "asc";
  draft.limit = "25";
  draft["where:0"] = { operator: "<", value: " 250 " };
  draft["where:1"] = { operator: "BETWEEN", value: ["2025-01-01", "2025-03-01"] };
  assert.deepEqual(changesFrom(controls, draft), {
    "agg:0": "MIN",
    sort: "asc",
    limit: 25,
    "where:0": { operator: "<", value: "250" },
    "where:1": { operator: "BETWEEN", value: ["2025-01-01", "2025-03-01"] },
  });
});

test("changing a value back counts as no change", () => {
  const draft = initialDraft(controls);
  draft["where:0"] = { operator: ">", value: "100" };
  assert.deepEqual(changesFrom(controls, draft), {});
});

test("obvious problems are caught before a run is spent", () => {
  const draft = initialDraft(controls);
  draft.limit = "0";
  assert.match(draftProblem(controls, changesFrom(controls, draft)), /between 1 and 1,000/);
  draft.limit = "2.5";
  assert.match(draftProblem(controls, changesFrom(controls, draft)), /between 1 and 1,000/);
  draft.limit = "";
  assert.match(draftProblem(controls, changesFrom(controls, draft)), /between 1 and 1,000/);
  draft.limit = "5";
  draft["where:0"] = { operator: ">", value: "lots" };
  assert.equal(draftProblem(controls, changesFrom(controls, draft)), "Price needs a number.");
  draft["where:0"] = { operator: ">", value: "" };
  assert.equal(draftProblem(controls, changesFrom(controls, draft)), "Price needs a value.");
  draft["where:0"] = { operator: ">", value: "1e3" };
  assert.equal(draftProblem(controls, changesFrom(controls, draft)), null);
});

test("labels read as words and follow the column type", () => {
  assert.equal(aggregateLabel(controls[0], "MIN"), "Lowest");
  assert.equal(aggregateLabel({ type: "date" }, "MAX"), "Latest");
  assert.equal(sortLabel(controls[1], "asc"), "Lowest first");
  assert.equal(sortLabel({ type: "date" }, "desc"), "Newest first");
  assert.equal(sortLabel({ type: "text" }, "asc"), "A to Z");
  assert.equal(operatorLabel(controls[3], ">="), "at least");
  assert.equal(operatorLabel({ type: "date" }, ">"), "after");
  assert.equal(operatorLabel(controls[4], "BETWEEN"), "between");
});

test("adjustments add up into one line", () => {
  assert.equal(joinAdjusted(null, ["MIN instead of MAX of price", "lowest first"]), "MIN instead of MAX of price; lowest first");
  assert.equal(joinAdjusted("lowest first", ["top 3"]), "lowest first; top 3");
  assert.equal(joinAdjusted("top 3", []), "top 3", "a plain re-run keeps the label");
  assert.equal(joinAdjusted(null, []), null);
  assert.equal(joinAdjusted("x".repeat(600), ["y"]).length, 500, "fits the stored field");
});

test("the label says what differs from the original, not every step", () => {
  assert.equal(joinAdjusted("MIN instead of MAX of price", ["AVG instead of MIN of price"]), "AVG instead of MAX of price");
  assert.equal(joinAdjusted("MIN instead of MAX of price", ["MAX instead of MIN of price"]), null, "back where it started");
  assert.equal(joinAdjusted("MIN instead of MAX of price; top 3", ["highest first"]), "MIN instead of MAX of price; top 3; highest first");
  assert.equal(joinAdjusted("lowest first; top 3", ["highest first", "top 25"]), "top 25", "two sort flips cancel");
  assert.equal(joinAdjusted("top 3 per category", ["top 5"]), "top 3 per category; top 5", "different limits stay apart");
  assert.equal(joinAdjusted("price > 100", ["price > 100"]), "price > 100");
});
