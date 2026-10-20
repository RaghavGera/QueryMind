import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Loader2, Play, SlidersHorizontal, Undo2 } from "lucide-react";
import { cn } from "../../lib/utils";
import {
  aggregateLabel,
  changesFrom,
  draftProblem,
  initialDraft,
  operatorLabel,
  sortLabel,
} from "../../lib/tweaks.js";

const FIELD =
  "rounded-md border border-white/10 bg-base-900 px-2 py-1 text-sm text-ink focus:border-accent-violet/50 focus:outline-none";

function Control({ title, children }) {
  return (
    <div role="group" aria-label={title} className="flex min-w-0 flex-col gap-1">
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-faint">{title}</span>
      <span className="flex flex-wrap items-center gap-1.5">{children}</span>
    </div>
  );
}

function ValueInput({ control, value, onChange, label }) {
  return (
    <input
      type={control.type === "date" ? "date" : "text"}
      inputMode={control.type === "number" ? "decimal" : undefined}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(FIELD, control.type === "date" ? "w-40" : "w-32")}
      aria-label={label}
    />
  );
}

/*
 * Change an answer without asking again: the function, sort, row count and
 * filter values its plan allows. The server rebuilds the SQL from the checked
 * plan (no AI call), so this doesn't use a question. Remount it (key) for each
 * new answer so the draft starts from that answer's values.
 */
export default function TweakBar({ controls, onRun, busy = false, error = null }) {
  const [draft, setDraft] = useState(() => initialDraft(controls));
  const changes = useMemo(() => changesFrom(controls, draft), [controls, draft]);
  const changed = Object.keys(changes).length > 0;
  const problem = changed ? draftProblem(controls, changes) : null;

  const set = (id, value) => setDraft((d) => ({ ...d, [id]: value }));
  const setFilter = (id, patch) => setDraft((d) => ({ ...d, [id]: { ...d[id], ...patch } }));

  const run = (e) => {
    e.preventDefault();
    if (changed && !problem && !busy) onRun(changes);
  };

  return (
    <motion.form
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      onSubmit={run}
      className="surface-card p-4"
      aria-label="Adjust this answer"
    >
      <p className="mb-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-ink-dim">
        <SlidersHorizontal size={14} className="text-accent-cyan" />
        Adjust this answer
      </p>

      <div className="flex flex-wrap items-end gap-x-5 gap-y-3">
        {controls.map((control) => {
          const value = draft[control.id];
          if (control.kind === "aggregate") {
            return (
              <Control key={control.id} title={control.label}>
                <select value={value} onChange={(e) => set(control.id, e.target.value)} className={FIELD} aria-label={`Function for ${control.label}`}>
                  {control.options.map((option) => (
                    <option key={option} value={option}>
                      {aggregateLabel(control, option)}
                    </option>
                  ))}
                </select>
              </Control>
            );
          }
          if (control.kind === "sort") {
            return (
              <Control key={control.id} title={`Sort by ${control.label}`}>
                <select value={value} onChange={(e) => set(control.id, e.target.value)} className={FIELD} aria-label={`Sort by ${control.label}`}>
                  {control.options.map((option) => (
                    <option key={option} value={option}>
                      {sortLabel(control, option)}
                    </option>
                  ))}
                </select>
              </Control>
            );
          }
          if (control.kind === "limit") {
            const perGroup = control.id === "per_group";
            return (
              <Control key={control.id} title={perGroup ? `Top N ${control.label}` : "Rows"}>
                <input
                  type="number"
                  min={control.min}
                  max={control.max}
                  step={1}
                  value={value}
                  placeholder="all"
                  onChange={(e) => set(control.id, e.target.value)}
                  className={cn(FIELD, "w-24")}
                  aria-label={perGroup ? `Rows ${control.label}` : "Number of rows"}
                />
              </Control>
            );
          }
          // A filter: operator plus one value (two for "between").
          const between = value.operator === "BETWEEN";
          const values = Array.isArray(value.value) ? value.value : [value.value];
          return (
            <Control key={control.id} title={control.label}>
              {control.operators.length > 1 ? (
                <select
                  value={value.operator}
                  onChange={(e) => setFilter(control.id, { operator: e.target.value })}
                  className={FIELD}
                  aria-label={`How to compare ${control.label}`}
                >
                  {control.operators.map((operator) => (
                    <option key={operator} value={operator}>
                      {operatorLabel(control, operator)}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-sm text-ink-dim">{operatorLabel(control, value.operator)}</span>
              )}
              {between ? (
                <>
                  <ValueInput control={control} value={values[0]} label={`${control.label} from`} onChange={(v) => setFilter(control.id, { value: [v, values[1]] })} />
                  <span className="text-sm text-ink-dim">and</span>
                  <ValueInput control={control} value={values[1]} label={`${control.label} to`} onChange={(v) => setFilter(control.id, { value: [values[0], v] })} />
                </>
              ) : (
                <ValueInput control={control} value={values[0]} label={`${control.label} value`} onChange={(v) => setFilter(control.id, { value: v })} />
              )}
            </Control>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!changed || Boolean(problem) || busy}
          className={cn("btn-primary !px-4 !py-1.5", (!changed || problem || busy) && "pointer-events-none opacity-50")}
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {busy ? "Running" : "Run"}
        </button>
        {changed && !busy && (
          <button type="button" onClick={() => setDraft(initialDraft(controls))} className="btn-ghost">
            <Undo2 size={14} />
            Undo changes
          </button>
        )}
        <span className="text-xs text-ink-faint">No AI call, so it doesn't use a question.</span>
      </div>

      {(problem || error) && (
        <p role="alert" className="mt-3 flex items-start gap-2 text-sm text-state-danger">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          {problem || error}
        </p>
      )}
    </motion.form>
  );
}
