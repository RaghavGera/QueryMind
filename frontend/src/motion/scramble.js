// "Decode" effect: characters left of the reveal point are final, the rest
// flicker through glyphs. Pure and deterministic for a given seed.

export const GLYPHS = "▚▞▛▜▙▟░▒▓<>/\\{}[]=+*#01";

function hash(i, seed) {
  let h = (i + 1) * 374761393 + seed * 668265263;
  h = (h ^ (h >>> 13)) * 1274126177;
  return Math.abs(h ^ (h >>> 16));
}

/**
 * @param {string} target  final text
 * @param {number} progress 0..1, how much of it is decoded
 * @param {number} seed     changes every frame to make the glyphs flicker
 */
export function scrambleText(target, progress, seed = 1) {
  const reveal = Math.floor(Math.min(1, Math.max(0, progress)) * target.length);
  let out = "";
  for (let i = 0; i < target.length; i += 1) {
    const ch = target[i];
    out += i < reveal || ch === " " || ch === "\n" ? ch : GLYPHS[hash(i, seed) % GLYPHS.length];
  }
  return out;
}
