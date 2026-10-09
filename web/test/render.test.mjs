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
  assert.equal(formatEvent({ type: "stage", data: { name: "cutoff", date: "2024-09-03" } }), "cutoff · 2024-09-03");
  assert.equal(formatEvent({ type: "stage", data: { name: "vendor", subject: "ACME LTD" } }), "vendor · ACME LTD");
  assert.equal(formatEvent({ type: "stage", data: { name: "pages", ms: 12.5 } }), "pages · 12.5 ms");
  const agent = { type: "agent", data: { tool: "search_maps", terms: "Acme Pune", hits: 2, credits: 1, why: "maps gap: city added", flagged: "" } };
  assert.equal(formatEvent(agent), '  agent search_maps "Acme Pune" · 2 hits · 1 cr · maps gap: city added');
  const hostile = { type: "agent", data: { tool: "search_web", terms: "x", hits: 0, credits: 0, why: "w", flagged: "ignore_previous" } };
  assert.match(formatEvent(hostile) ?? "", /\[flagged ignore_previous\]/);
  assert.equal(formatEvent({ type: "signal", data: {} }), null);
});

test("status marks use the plain words", () => {
  assert.equal(MARKS.inconsistent, "doesn't match");
});
