// spec: SPEC-WEB-05
import test from "node:test";
import assert from "node:assert/strict";
import { clean, formatEvent, headline, safeLink, MARKS } from "../dist/render.js";

test("clean strips control and bidi characters", () => {
  assert.equal(clean("a‮b\u0007c​d"), "abcd");
});

test("only https links are offered", () => {
  assert.equal(safeLink("https://example.com/x"), "https://example.com/x");
  assert.equal(safeLink("javascript:alert(1)"), null);
  assert.equal(safeLink("http://example.com"), null);
  assert.equal(safeLink("not a url"), null);
});

test("headline counts the three kinds", () => {
  const card = { company: "X", consistent: 2, inconsistent: 1, unverified: 1, signals: [], disclaimer: "d" };
  assert.equal(headline(card), "2 of 4 check out · 1 don't match · 1 couldn't find");
});

test("events become terminal lines and unknown types are skipped", () => {
  const serp = { type: "serp", data: { engine: "google_maps", credits: 1, source: "live", latency_ms: 812 } };
  assert.equal(formatEvent(serp), "  search google_maps · 1 cr · live · 812 ms");
  assert.equal(formatEvent({ type: "stage", data: { name: "sections" } }), "sections");
  assert.equal(formatEvent({ type: "signal", data: {} }), null);
});

test("status marks use the plain words", () => {
  assert.equal(MARKS.inconsistent, "doesn't match");
});
