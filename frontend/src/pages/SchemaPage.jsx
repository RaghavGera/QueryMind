import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { getSchema } from "../services/schemaApi";
import SchemaTableCard from "../components/schema/SchemaTableCard";
import SchemaRelationships from "../components/schema/SchemaRelationships";

export default function SchemaPage() {
  const [schema, setSchema] = useState(null);
  const [active, setActive] = useState(null);

  useEffect(() => {
    getSchema().then(setSchema);
  }, []);

  if (!schema) {
    return (
      <div className="flex h-64 items-center justify-center gap-2 text-ink-dim">
        <Loader2 size={16} className="animate-spin" /> Loading schema...
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 sm:px-6 py-10">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink">Database schema</h1>
        <p className="mt-1 text-sm text-ink-dim">{schema.tables.length} tables · sample_ecommerce_db</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {schema.tables.map((table) => (
          <SchemaTableCard
            key={table.name}
            table={table}
            active={active === table.name}
            onClick={() => setActive((a) => (a === table.name ? null : table.name))}
          />
        ))}
      </div>

      <SchemaRelationships relationships={schema.relationships} />
    </div>
  );
}
