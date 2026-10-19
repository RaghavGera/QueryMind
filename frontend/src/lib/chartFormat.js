// Labels for chart axes and tooltips.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?(?:Z|[+-]\d{2}:?\d{2})?$/;

/**
 * Calendar parts of an ISO date or timestamp, as written. No timezone
 * conversion: a month bucket "2025-06-01T00:00:00+05:30" is June for every
 * viewer, wherever they are.
 */
export function dateParts(value) {
  if (typeof value !== "string") return null;
  const m = ISO_DATE.exec(value.trim());
  if (!m) return null;
  const [, year, month, day, hour = "00", minute = "00", second = "00"] = m;
  if (Number(month) < 1 || Number(month) > 12 || Number(day) < 1 || Number(day) > 31) return null;
  return {
    year: Number(year),
    month: Number(month),
    day: Number(day),
    time: `${hour}:${minute}`,
    midnight: hour === "00" && minute === "00" && second === "00",
  };
}

/**
 * A label function for a column of dates, or null when the values aren't all
 * dates. Buckets get the coarsest honest label: "2025" when every value is
 * 1 January (and there are several years), "Jun 2025" when every value is the
 * 1st of a month, "3 Jun 2025" for dates, and the time as well otherwise.
 */
export function dateLabeler(values) {
  const parts = values.map(dateParts);
  if (!parts.length || parts.some((p) => !p)) return null;
  const midnight = parts.every((p) => p.midnight);
  const firstOfMonth = midnight && parts.every((p) => p.day === 1);
  const years = new Set(parts.map((p) => p.year));
  const label = (format) => (value) => {
    const p = dateParts(value);
    return p ? format(p) : String(value ?? "");
  };
  if (firstOfMonth && years.size > 1 && parts.every((p) => p.month === 1)) return label((p) => String(p.year));
  if (firstOfMonth) return label((p) => `${MONTHS[p.month - 1]} ${p.year}`);
  if (midnight) return label((p) => `${p.day} ${MONTHS[p.month - 1]} ${p.year}`);
  return label((p) => `${p.day} ${MONTHS[p.month - 1]} ${p.year} ${p.time}`);
}

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });

/** 280000 -> "280K", 1550630 -> "1.6M": short enough for an axis. */
export function compactNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? compact.format(value) : String(value ?? "");
}

/** 706939 -> "706,939": the full value, for tooltips. */
export function fullNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en", { maximumFractionDigits: 2 }) : value;
}
