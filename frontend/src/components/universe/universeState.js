/*
 * Shared signals between the landing chapters (DOM, scroll-driven) and the
 * WebGL universe. Chapters write, the canvas reads every frame inside
 * useFrame, so scrolling never re-renders React. All values are 0..1.
 */
export const universe = {
  travel: 0, // whole-page scroll progress: flies the camera through the stars
  constellation: 0, // schema constellation visibility (chapter 02)
  highlight: 0, // tables used by the question light up
  beam: 0, // query beam from the question into the schema
  amber: 0, // ambiguity tint (chapter 03)
  magenta: 0, // answer tint (chapter 05)
  warp: 0, // scroll-driven warp (launch chapter)
  warpBoost: 0, // click-driven warp (Launch button)
};

export function resetUniverse() {
  Object.keys(universe).forEach((key) => {
    universe[key] = 0;
  });
}
