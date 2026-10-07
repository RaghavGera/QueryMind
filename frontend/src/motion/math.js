// Pure helpers shared by scroll-driven scenes (unit-tested with node --test).

export const clamp01 = (v) => Math.min(1, Math.max(0, v));

/** Progress of ``p`` inside [start, end], clamped to 0..1. */
export function segment(p, start, end) {
  if (end <= start) return p >= end ? 1 : 0;
  return clamp01((p - start) / (end - start));
}

/** Rises over [inStart, inEnd], holds at 1, falls over [outStart, outEnd]. */
export function bump(p, inStart, inEnd, outStart, outEnd) {
  return Math.min(segment(p, inStart, inEnd), 1 - segment(p, outStart, outEnd));
}

export const lerp = (a, b, t) => a + (b - a) * t;

export const easeOutCubic = (t) => 1 - (1 - t) ** 3;

export const easeInOutCubic = (t) => (t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2);

/** How many characters of a ``length``-long string are visible at ``progress``. */
export function visibleChars(progress, length) {
  return Math.round(clamp01(progress) * length);
}

/** Integer formatting used by count-up numbers ("734,561"). */
export function formatInt(n) {
  return Math.round(n).toLocaleString("en-US");
}
