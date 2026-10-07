import { test } from "node:test";
import assert from "node:assert/strict";
import { toSchemaView } from "./schemaShape.js";

const API = {
  database: "text_to_sql",
  tables: {
    orders: {
      columns: {
        order_id: { data_type: "integer", is_nullable: false, is_primary_key: true },
        customer_id: { data_type: "integer", is_nullable: true, is_primary_key: false },
      },
      primary_keys: ["order_id"],
      foreign_keys: [{ column: "customer_id", references: "customers.customer_id" }],
    },
    customers: {
      columns: { customer_id: { data_type: "integer", is_nullable: false, is_primary_key: true } },
      primary_keys: ["customer_id"],
      foreign_keys: [],
    },
  },
};

test("the /schema response becomes tables, columns and relationships", () => {
  const view = toSchemaView(API);
  assert.equal(view.database, "text_to_sql");
  assert.deepEqual(view.tables.map((t) => t.name), ["customers", "orders"], "sorted by name");
  assert.deepEqual(view.tables[1].columns, [
    { name: "order_id", type: "integer", pk: true, fk: null, nullable: false },
    { name: "customer_id", type: "integer", pk: false, fk: "customers.customer_id", nullable: true },
  ]);
  assert.deepEqual(view.relationships, [{ from: "orders", to: "customers", label: "customer_id" }]);
  assert.ok(view.tables.every((t) => !("rowCount" in t)), "no invented row counts");
});

test("an empty or missing response gives an empty schema", () => {
  assert.deepEqual(toSchemaView(null), { database: null, tables: [], relationships: [] });
});
