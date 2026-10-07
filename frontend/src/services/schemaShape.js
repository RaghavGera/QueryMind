/**
 * Convert GET /schema (app/schema.py DatabaseSchema.to_dict + "database")
 * into what the Schema tab renders:
 *   { database, tables: [{ name, columns: [{ name, type, pk, fk, nullable }] }],
 *     relationships: [{ from, to, label }] }
 * No row counts: the API doesn't report them, so none are shown.
 */
export function toSchemaView(api) {
  const tables = Object.entries(api?.tables || {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, table]) => {
      const fks = Object.fromEntries((table.foreign_keys || []).map((fk) => [fk.column, fk.references]));
      const pks = new Set(table.primary_keys || []);
      const columns = Object.entries(table.columns || {}).map(([column, info]) => ({
        name: column,
        type: info.data_type,
        pk: Boolean(info.is_primary_key || pks.has(column)),
        fk: fks[column] || null,
        nullable: Boolean(info.is_nullable),
      }));
      return { name, columns };
    });

  const relationships = Object.entries(api?.tables || {}).flatMap(([name, table]) =>
    (table.foreign_keys || []).map((fk) => ({ from: name, to: fk.references.split(".")[0], label: fk.column })),
  );

  return { database: api?.database || null, tables, relationships };
}
