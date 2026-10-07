import { Check } from "lucide-react";
import PinnedChapter, { useSegment } from "../../../motion/PinnedChapter";
import { Appear, ChapterHeading, TypedCode } from "./shared";

// Exactly what app/sql_generator.py produces for the showcase question
// (captured from the generator on 2026-10-07).
export const SHOWCASE_SQL = `SELECT "customers"."country", SUM("order_items"."quantity" * "order_items"."unit_price") AS "sum_order_items_quantity_order_items_unit_price"
FROM "orders"
INNER JOIN "customers" ON "orders"."customer_id" = "customers"."customer_id"
INNER JOIN "order_items" ON "orders"."order_id" = "order_items"."order_id"
GROUP BY "customers"."country"
ORDER BY SUM("order_items"."quantity" * "order_items"."unit_price") DESC
LIMIT 1`;

// Only guarantees the backend enforces today.
const CHECKS = [
  "Tables and columns verified against the live schema",
  "Values sent as parameters, never pasted into the SQL",
  "Inserts and updates previewed, and run only after you confirm",
  "DELETE is never executed",
];

function Sql() {
  const typing = useSegment(0.06, 0.58);

  return (
    <div className="mx-auto grid h-full max-w-7xl grid-cols-1 content-center items-center gap-6 px-5 pt-16 sm:gap-10 sm:px-6 lg:grid-cols-[4fr_8fr] lg:gap-14">
      <ChapterHeading index="04" label="Generated, never hand-written" title="Then it writes the SQL." compact>
        A generator builds it from the resolved intent: every identifier quoted and checked, every value a parameter.
      </ChapterHeading>

      <div className="min-w-0 space-y-4 sm:space-y-5">
        <div className="hud">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-accent-magenta/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-accent-amber/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-accent-cyan/70" />
            </div>
            <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">query.sql · PostgreSQL</span>
          </div>
          <div className="px-4 py-5 sm:px-5">
            <TypedCode progress={typing} code={SHOWCASE_SQL} className="max-sm:text-[11px]" />
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2" role="list">
          {CHECKS.map((check, i) => (
            <Appear key={check} at={0.56 + i * 0.07}>
              <div role="listitem" className="flex items-start gap-2.5 rounded-xl border border-accent-cyan/15 bg-accent-cyan/[0.05] px-3.5 py-2 text-xs text-ink sm:py-2.5 sm:text-sm">
                <Check size={15} className="mt-0.5 shrink-0 text-accent-cyan" />
                {check}
              </div>
            </Appear>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function SqlChapter() {
  return (
    <PinnedChapter id="sql" length={2.4}>
      <Sql />
    </PinnedChapter>
  );
}
