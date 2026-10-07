/**
 * Split ``text`` into segments, tagging whole-word matches of ``words``
 * ({ word: className }). Used to light up recognized entities as they type.
 */
export function splitHighlights(text, words = {}) {
  const keys = Object.keys(words);
  if (!keys.length) return [{ text, className: null }];
  const pattern = new RegExp(`\\b(${keys.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`, "gi");
  const segments = [];
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) segments.push({ text: text.slice(last, match.index), className: null });
    segments.push({ text: match[0], className: words[match[0].toLowerCase()] ?? null });
    last = match.index + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), className: null });
  return segments;
}

/**
 * The visible part of each segment when ``count`` characters are typed.
 * A highlight applies only once its whole word is visible.
 */
export function typedSegments(segments, count) {
  let remaining = count;
  const out = [];
  for (const seg of segments) {
    if (remaining <= 0) break;
    const visible = seg.text.slice(0, remaining);
    out.push({ text: visible, className: visible.length === seg.text.length ? seg.className : null });
    remaining -= visible.length;
  }
  return out;
}

/**
 * Truncate highlighted lines (arrays of { text, cls } tokens) to the first
 * ``count`` characters, counting one character per line break. Lines not
 * reached yet are dropped. Used by the code "typing" effects.
 */
export function sliceLines(lines, count) {
  const out = [];
  let remaining = count;
  for (const tokens of lines) {
    if (remaining < 0) break;
    const visible = [];
    for (const tok of tokens) {
      if (remaining <= 0) break;
      const text = tok.text.slice(0, remaining);
      visible.push({ ...tok, text });
      remaining -= text.length;
    }
    out.push(visible);
    remaining -= 1; // the newline
  }
  return out;
}
