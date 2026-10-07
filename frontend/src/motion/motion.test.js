import { test } from "node:test";
import assert from "node:assert/strict";
import { bump, clamp01, easeInOutCubic, easeOutCubic, formatInt, segment, visibleChars } from "./math.js";
import { GLYPHS, scrambleText } from "./scramble.js";

const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} != ${expected}`);

test("segment maps a window of the scroll to 0..1", () => {
  assert.equal(segment(0.1, 0.2, 0.6), 0);
  near(segment(0.4, 0.2, 0.6), 0.5);
  assert.equal(segment(0.9, 0.2, 0.6), 1);
  assert.equal(segment(0.5, 0.5, 0.5), 1, "zero-width window acts as a step");
});

test("bump rises, holds and falls", () => {
  assert.equal(bump(0, 0.1, 0.2, 0.8, 0.9), 0);
  near(bump(0.15, 0.1, 0.2, 0.8, 0.9), 0.5);
  assert.equal(bump(0.5, 0.1, 0.2, 0.8, 0.9), 1);
  near(bump(0.85, 0.1, 0.2, 0.8, 0.9), 0.5);
  assert.equal(bump(1, 0.1, 0.2, 0.8, 0.9), 0);
});

test("easings start at 0 and end at 1", () => {
  for (const ease of [easeOutCubic, easeInOutCubic]) {
    assert.equal(ease(0), 0);
    assert.equal(ease(1), 1);
  }
  assert.equal(clamp01(-2), 0);
  assert.equal(clamp01(3), 1);
});

test("typing reveals characters proportionally", () => {
  assert.equal(visibleChars(0, 40), 0);
  assert.equal(visibleChars(0.5, 40), 20);
  assert.equal(visibleChars(2, 40), 40);
});

test("count-up numbers are formatted like 734,561", () => {
  assert.equal(formatInt(734561), "734,561");
  assert.equal(formatInt(0.4), "0");
});

test("scramble keeps length and spaces, and resolves fully at 1", () => {
  const target = "Ask your database.";
  const mid = scrambleText(target, 0.5, 7);
  assert.equal(mid.length, target.length);
  assert.equal(mid[3], " ", "spaces never scramble");
  assert.equal(mid.slice(0, 9), target.slice(0, 9), "revealed part is final");
  for (const ch of mid.slice(10).replace(/ /g, "")) assert.ok(GLYPHS.includes(ch));
  assert.equal(scrambleText(target, 1, 3), target);
  assert.equal(scrambleText(target, 0.2, 5), scrambleText(target, 0.2, 5), "deterministic per seed");
});

import { splitHighlights, typedSegments } from "./text.js";

test("entity words are split out with their highlight class", () => {
  const segs = splitHighlights("Which region generated the most revenue?", { region: "cyan", revenue: "violet" });
  assert.deepEqual(segs.map((s) => [s.text, s.className]), [
    ["Which ", null],
    ["region", "cyan"],
    [" generated the most ", null],
    ["revenue", "violet"],
    ["?", null],
  ]);
  assert.deepEqual(splitHighlights("plain", {}), [{ text: "plain", className: null }]);
  assert.equal(splitHighlights("regional sales", { region: "cyan" })[0].className, null, "whole words only");
});

test("a highlight appears only once its word is fully typed", () => {
  const segs = splitHighlights("Which region", { region: "cyan" });
  assert.deepEqual(typedSegments(segs, 9), [{ text: "Which ", className: null }, { text: "reg", className: null }]);
  assert.deepEqual(typedSegments(segs, 12), [{ text: "Which ", className: null }, { text: "region", className: "cyan" }]);
  assert.deepEqual(typedSegments(segs, 0), []);
});

import { highlightJsonLine } from "../lib/sqlHighlight.js";

test("JSON lines are tokenized into keys, strings, numbers and literals", () => {
  const toks = highlightJsonLine('  "country": "India", "n": 734561.0, "x": null');
  const byText = Object.fromEntries(toks.map((t) => [t.text.trim(), t.cls]));
  assert.equal(byText['"country":'], "text-[#c9c2ff]");
  assert.equal(byText['"India"'], "text-accent-cyan");
  assert.equal(byText["734561.0"], "text-accent-magenta");
  assert.equal(byText.null, "text-accent-amber");
  assert.equal(toks.map((t) => t.text).join(""), '  "country": "India", "n": 734561.0, "x": null', "lossless");
});

import { sliceLines } from "./text.js";

test("code typing reveals whole lines, then part of the next", () => {
  const lines = [[{ text: "SELECT", cls: "k" }, { text: " 1", cls: "n" }], [{ text: "FROM t", cls: "k" }]];
  assert.deepEqual(sliceLines(lines, 0), [[]]);
  assert.deepEqual(sliceLines(lines, 7), [[{ text: "SELECT", cls: "k" }, { text: " ", cls: "n" }]]);
  assert.deepEqual(sliceLines(lines, 10), [[{ text: "SELECT", cls: "k" }, { text: " 1", cls: "n" }], [{ text: "F", cls: "k" }]], "8 chars + newline + 1");
  assert.equal(sliceLines(lines, 99).length, 2);
});
