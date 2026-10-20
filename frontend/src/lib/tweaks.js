/*
 * Quick tweaks: the controls an answer offers (from the backend, see
 * app/tweaks.py describe) turned into readable labels, a draft the user edits,
 * and the minimal set of changes sent to POST /query/tweak.
 */

const AGGREGATE_WORDS = {
  number: { MAX: "Highest", MIN: "Lowest", AVG: "Average", SUM: "Total", COUNT: "Count" },
  date: { MAX: "Latest", MIN: "Earliest", COUNT: "Count" },
  text: { MAX: "Last (A to Z)", MIN: "First (A to Z)", COUNT: "Count" },
};

const SORT_WORDS = {
  number: { desc: "Highest first", asc: "Lowest first" },
  date: { desc: "Newest first", asc: "Oldest first" },
  text: { desc: "Z to A", asc: "A to Z" },
};

const OPERATOR_WORDS = {
  number: { "=": "is", "!=": "is not", ">": "more than", "<": "less than", ">=": "at least", "<=": "at most" },
  date: { "=": "on", "!=": "not on", ">": "after", "<": "before", ">=": "on or after", "<=": "on or before" },
  text: { "=": "is", "!=": "is not" },
};

export function aggregateLabel(control, option) {
  return (AGGREGATE_WORDS[control.type] || AGGREGATE_WORDS.number)[option] || option;
}

export function sortLabel(control, option) {
  return (SORT_WORDS[control.type] || SORT_WORDS.number)[option] || option;
}

export function operatorLabel(control, operator) {
  if (operator === "BETWEEN") return "between";
  return (OPERATOR_WORDS[control.type] || OPERATOR_WORDS.text)[operator] || operator;
}

const asText = (value) => (value === null || value === undefined ? "" : String(value));

/** The editable state for each control, starting from the answer's own values. */
export function initialDraft(controls) {
  const draft = {};
  for (const control of controls || []) {
    if (control.kind === "filter") {
      const value = Array.isArray(control.value) ? control.value.map(asText) : asText(control.value);
      draft[control.id] = { operator: control.operator, value };
    } else {
      draft[control.id] = asText(control.value);
    }
  }
  return draft;
}

/** Only what differs from the answer, in the shape the backend expects. */
export function changesFrom(controls, draft) {
  const changes = {};
  for (const control of controls || []) {
    const edited = draft?.[control.id];
    if (edited === undefined) continue;
    if (control.kind === "filter") {
      const original = Array.isArray(control.value) ? control.value.map(asText) : asText(control.value);
      const value = Array.isArray(edited.value) ? edited.value.map((v) => v.trim()) : edited.value.trim();
      if (edited.operator !== control.operator || JSON.stringify(value) !== JSON.stringify(original)) {
        changes[control.id] = { operator: edited.operator, value };
      }
    } else if (control.kind === "limit") {
      const value = edited.trim();
      if (value !== asText(control.value)) changes[control.id] = value === "" ? null : Number(value);
    } else if (edited !== asText(control.value)) {
      changes[control.id] = edited;
    }
  }
  return changes;
}

/** A problem to show before sending, or null. The server checks everything again. */
export function draftProblem(controls, changes) {
  for (const control of controls || []) {
    const change = changes[control.id];
    if (change === undefined) continue;
    if (control.kind === "limit" && !(Number.isInteger(change) && change >= control.min && change <= control.max)) {
      return `Show between ${control.min} and ${control.max.toLocaleString("en")} rows.`;
    }
    if (control.kind === "filter") {
      const values = Array.isArray(change.value) ? change.value : [change.value];
      if (values.some((v) => v === "")) return `${capitalize(control.label)} needs a value.`;
      if (control.type === "number" && values.some((v) => !Number.isFinite(Number(v)))) {
        return `${capitalize(control.label)} needs a number.`;
      }
    }
  }
  return null;
}

function capitalize(text) {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

const AGGREGATE_CHANGE = /^(\w+) instead of (\w+) of (.+)$/;
const SORT_CHANGE = new Set(["highest first", "lowest first", "newest first", "oldest first", "Z to A", "A to Z"]);
const TOP_CHANGE = /^top \d+( .+)?$/;

/** Fold one new change into the list, so the label says what differs from the original. */
function fold(parts, change) {
  const agg = change.match(AGGREGATE_CHANGE);
  if (agg) {
    const [, now, was, column] = agg;
    const i = parts.findIndex((p) => p.match(AGGREGATE_CHANGE)?.[3] === column && p.match(AGGREGATE_CHANGE)[1] === was);
    if (i < 0) return [...parts, change];
    const first = parts[i].match(AGGREGATE_CHANGE)[2];
    const rest = parts.filter((_, j) => j !== i);
    return now === first ? rest : [...rest.slice(0, i), `${now} instead of ${first} of ${column}`, ...rest.slice(i)];
  }
  if (SORT_CHANGE.has(change)) {
    // Each sort change is a flip, so a second one is back to the original order.
    const i = parts.findIndex((p) => SORT_CHANGE.has(p));
    return i < 0 ? [...parts, change] : parts.filter((_, j) => j !== i);
  }
  const top = change.match(TOP_CHANGE);
  if (top) {
    const i = parts.findIndex((p) => p.match(TOP_CHANGE) && p.match(TOP_CHANGE)[1] === top[1]);
    return i < 0 ? [...parts, change] : parts.map((p, j) => (j === i ? change : p));
  }
  return parts.includes(change) ? parts : [...parts, change];
}

/** Changes so far plus this run's, as one line ("MIN instead of MAX of price; lowest first"). */
export function joinAdjusted(previous, summary) {
  const parts = (summary || []).reduce(fold, previous ? previous.split("; ") : []);
  if (!parts.length) return null;
  const line = parts.join("; ");
  return line.length > 500 ? `${line.slice(0, 499)}…` : line;
}
