import { ArrowRight } from "lucide-react";
import PinnedChapter from "../../../motion/PinnedChapter";
import { bump, segment } from "../../../motion/math";
import { Appear, ChapterHeading, useUniverseSignal } from "./shared";

// What the extractor really does with the showcase question: "revenue" is
// arithmetic over real columns, and "region" maps to the closest real column
// (the demo schema has customers.country, no region column).
const MAPPINGS = [
  { word: "“revenue”", to: "SUM(order_items.quantity × order_items.unit_price)", note: "metric = arithmetic over real columns" },
  { word: "“region”", to: "customers.country", note: "closest real column: there is no region column" },
  { word: "joins", to: "orders → customers · order_items → orders", note: "taken from your foreign keys" },
];

function Schema() {
  useUniverseSignal("constellation", (p) => bump(p, 0, 0.14, 0.86, 1));
  useUniverseSignal("beam", (p) => segment(p, 0.06, 0.38));
  useUniverseSignal("highlight", (p) => segment(p, 0.32, 0.55));

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col justify-start px-6 pt-28 lg:justify-center lg:pt-16">
      <div className="max-w-xl">
        <ChapterHeading index="02" label="Your schema" title="Words land on real columns.">
          QueryMind reads your live schema first, so every name in the SQL exists in your database.
        </ChapterHeading>

        <div className="mt-10 space-y-3">
          {MAPPINGS.map((m, i) => (
            <Appear key={m.word} at={0.3 + i * 0.13} x={-24} y={0}>
              <div className="hud px-5 py-4">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[13px]">
                  <span className="text-accent-glow">{m.word}</span>
                  <ArrowRight size={14} className="text-ink-faint" />
                  <span className="text-accent-cyan">{m.to}</span>
                </div>
                <p className="mt-1.5 text-xs text-ink-faint">{m.note}</p>
              </div>
            </Appear>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function SchemaChapter() {
  return (
    <PinnedChapter id="schema" length={2.4}>
      <Schema />
    </PinnedChapter>
  );
}
