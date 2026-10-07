import { useEffect, useRef } from "react";
import { animate, useInView, useMotionValue } from "framer-motion";
import { TypedCode } from "../components/landing/chapters/shared";
import { highlightJsonLine } from "../lib/sqlHighlight";
import { useReducedMotion } from "../hooks/useReducedMotion";
import ScrambleText from "../motion/ScrambleText";

const BASE_URL = "https://querymind-crln.onrender.com";

const REQUEST = `curl -X POST ${BASE_URL}/query \\
  -H "Content-Type: application/json" \\
  -d '{"question": "Which region generated the most revenue?"}'`;

// The real response, captured from POST /query on 2026-10-07 (demo database).
const RESPONSE = `{
  "status": "success",
  "sql": "SELECT \\"customers\\".\\"country\\", SUM(\\"order_items\\".\\"quantity\\" * \\"order_items\\".\\"unit_price\\") AS ... LIMIT 1",
  "params": [],
  "warnings": [],
  "clarification_questions": [],
  "error_message": null,
  "has_ambiguities": false,
  "result": {
    "columns": ["country", "sum_order_items_quantity_order_items_unit_price"],
    "rows": [{ "country": "India", "sum_order_items_quantity_order_items_unit_price": 734561.0 }]
  }
}`;

const ENDPOINTS = [
  { method: "POST", path: "/query", detail: "Ask a question. Returns the SQL, its parameters and the rows, or the clarification questions it needs answered." },
  { method: "POST", path: "/query/confirm", detail: "Run a previewed insert/update with its single-use confirmation token (only when writes are enabled on the server)." },
  { method: "GET", path: "/schema", detail: "The live schema: tables, columns, primary and foreign keys, and the database name." },
  { method: "GET", path: "/health", detail: "Database connectivity, and whether writes are enabled on this server." },
];

const OPTIONS = [
  { field: "question", type: "string", detail: "Required. The question in plain English." },
  { field: "clarification_context", type: "string | null", detail: "Your answer to a clarification question, sent with the original question." },
  { field: "strict", type: "boolean = true", detail: "false: answer ambiguous questions with the model's best guess and report it in warnings instead of asking." },
  { field: "allow_writes", type: "boolean = true", detail: "false: block inserts/updates for this request (preview only)." },
];

/** Terminal that types the request, then streams the response, once in view. */
function Terminal() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-15% 0px" });
  const reduced = useReducedMotion();
  const request = useMotionValue(reduced ? 1 : 0);
  const response = useMotionValue(reduced ? 1 : 0);

  useEffect(() => {
    if (!inView || reduced) return undefined;
    const typing = animate(request, 1, { duration: 1.6, ease: "linear" });
    const streaming = animate(response, 1, { duration: 1.4, delay: 2.0, ease: "easeOut" });
    return () => {
      typing.stop();
      streaming.stop();
    };
  }, [inView, reduced, request, response]);

  return (
    <div ref={ref} className="hud">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-accent-magenta/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-accent-amber/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-accent-cyan/70" />
        </div>
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">terminal</span>
      </div>
      <div className="space-y-4 px-5 py-5" data-lenis-prevent>
        <div className="flex gap-3">
          <span className="select-none font-mono text-[13px] text-accent-cyan">$</span>
          <TypedCode progress={request} code={REQUEST} numbers={false} highlight={(l) => [{ text: l, cls: "text-ink" }]} />
        </div>
        <TypedCode progress={response} code={RESPONSE} numbers={false} highlight={highlightJsonLine} className="max-h-[420px] overflow-auto" />
      </div>
    </div>
  );
}

export default function Developers() {
  return (
    <>
      <section className="mx-auto max-w-4xl px-6 pb-12 pt-36 text-center">
        <p className="hud-label mb-6">Developers</p>
        <ScrambleText as="h1" text="Query your database from code." trigger="mount" className="display-lg block" innerClassName="text-gradient" />
        <p className="mx-auto mt-6 max-w-xl text-lg text-ink-dim">
          The same engine behind the app, as a JSON API. No key needed today; one POST and you get SQL and rows back.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-20">
        <Terminal />
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-20">
        <p className="hud-label mb-6">Endpoints</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {ENDPOINTS.map((e) => (
            <div key={e.path} className="hud p-5">
              <p className="font-mono text-sm">
                <span className={e.method === "POST" ? "text-accent-magenta" : "text-accent-cyan"}>{e.method}</span>{" "}
                <span className="text-ink">{e.path}</span>
              </p>
              <p className="mt-2 text-sm leading-relaxed text-ink-dim">{e.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-32">
        <p className="hud-label mb-6">POST /query options</p>
        <div className="hud divide-y divide-white/[0.06]">
          {OPTIONS.map((o) => (
            <div key={o.field} className="grid gap-1 px-5 py-4 sm:grid-cols-[220px_160px_1fr] sm:gap-4">
              <span className="font-mono text-sm text-[#c9c2ff]">{o.field}</span>
              <span className="font-mono text-xs text-ink-faint sm:pt-0.5">{o.type}</span>
              <span className="text-sm text-ink-dim">{o.detail}</span>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-ink-faint">
          Base URL: <span className="font-mono text-ink-dim">{BASE_URL}</span>. Answers usually take a few seconds: each question
          makes one call to the language model.
        </p>
      </section>
    </>
  );
}
