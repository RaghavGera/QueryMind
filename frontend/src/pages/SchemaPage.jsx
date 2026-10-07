import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, RotateCw } from "lucide-react";
import { getSchema } from "../services/schemaApi";
import SchemaTableCard from "../components/schema/SchemaTableCard";
import SchemaRelationships from "../components/schema/SchemaRelationships";
import PageHeader from "../components/ui/PageHeader";

/** The live schema from GET /schema (no mock data, no invented row counts). */
export default function SchemaPage() {
  const [state, setState] = useState({ schema: null, error: null });
  const [attempt, setAttempt] = useState(0);
  const [active, setActive] = useState(null);

  useEffect(() => {
    let alive = true;
    getSchema({ refresh: attempt > 0 })
      .then((schema) => alive && setState({ schema, error: null }))
      .catch((error) => alive && setState({ schema: null, error: error.message }));
    return () => {
      alive = false;
    };
  }, [attempt]);

  const { schema, error } = state;

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-10 sm:px-6">
      <PageHeader
        label="Schema"
        title="Your database, as QueryMind sees it."
        detail={schema ? `${schema.database} · ${schema.tables.length} tables · ${schema.relationships.length} foreign keys` : "Read live from the backend."}
      />

      {error ? (
        <div className="hud flex flex-wrap items-center justify-between gap-3 p-5 text-sm text-state-danger">
          <span className="flex items-center gap-2">
            <AlertTriangle size={16} /> Could not load the schema: {error}
          </span>
          <button
            onClick={() => {
              setState({ schema: null, error: null });
              setAttempt((n) => n + 1);
            }}
            className="btn-ghost"
          >
            <RotateCw size={14} /> Retry
          </button>
        </div>
      ) : !schema ? (
        <div className="flex h-64 items-center justify-center gap-2 text-ink-dim">
          <Loader2 size={16} className="animate-spin" /> Reading the live schema…
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {schema.tables.map((table, i) => (
              <SchemaTableCard
                key={table.name}
                table={table}
                index={i}
                active={active === table.name}
                onClick={() => setActive((a) => (a === table.name ? null : table.name))}
              />
            ))}
          </div>
          <SchemaRelationships relationships={schema.relationships} />
        </>
      )}
    </div>
  );
}
