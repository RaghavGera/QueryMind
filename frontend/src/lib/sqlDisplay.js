// Display helpers for generated SQL and its results (pure; tested with node --test).

/** A parameter value as a SQL literal, for display and copy only. */
export function sqlLiteral(value) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "NULL";
  if (typeof value === "boolean") return value ? "TRUE" : "FALSE";
  if (Array.isArray(value)) return `(${value.map(sqlLiteral).join(", ")})`;
  return `'${String(value).replace(/'/g, "''")}'`;
}

/**
 * Replace psycopg's %s placeholders with the bound values, in order, so the
 * SQL is readable and runnable as shown. "%%" (an escaped percent) becomes
 * "%". The server still sends the values separately as parameters.
 */
export function inlineParams(sql, params = []) {
  if (!sql) return sql;
  let i = 0;
  return sql.replace(/%%|%s/g, (token) => {
    if (token === "%%") return "%";
    if (i >= params.length) return token; // more placeholders than values: leave visible
    return sqlLiteral(params[i++]);
  });
}

/** "sum_quantity_x_unit_price" -> "Sum quantity × unit price". */
export function humanizeColumn(name) {
  if (!name) return name;
  const text = String(name)
    .replace(/_x_/g, " × ")
    .replace(/_per_/g, " / ")
    .replace(/_plus_/g, " + ")
    .replace(/_minus_/g, " − ")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
