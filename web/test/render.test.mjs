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

import { caseBlurb, caseLabel, host, lineKind, shares } from "../dist/render.js";

test("lines are coloured by what produced them", () => {
  assert.equal(lineKind({ type: "serp", data: {} }), "serp");
  assert.equal(lineKind({ type: "agent", data: {} }), "agent");
  assert.equal(lineKind({ type: "stage", data: {} }), "stage");
  assert.equal(lineKind({ type: "signal", data: {} }), "stage");
});

test("a proof chip shows the host, and only for https links", () => {
  assert.equal(host("https://www.zaubacorp.com/company/X"), "zaubacorp.com");
  assert.equal(host("javascript:alert(1)"), "");
});

test("the meter shares add up and an empty card gives zeros", () => {
  const card = { company: "X", consistent: 8, inconsistent: 1, unverified: 1, signals: [], disclaimer: "d" };
  assert.deepEqual(shares(card), { ok: 80, bad: 10, none: 10 });
  assert.deepEqual(shares({ ...card, consistent: 0, inconsistent: 0, unverified: 0 }), { ok: 0, bad: 0, none: 0 });
});

test("case names get readable labels, unknown ones pass through", () => {
  assert.equal(caseLabel("tbi-corn"), "TBI Corn");
  assert.equal(caseLabel("new-case"), "new-case");
  assert.equal(caseBlurb("trafiksol"), "The case that made the news");
  assert.equal(caseBlurb("new-case"), "Recorded case");
});

import { parseEvents } from "../dist/render.js";

test("a bundle's events file becomes events, blank lines skipped", () => {
  const text = '{"type":"stage","data":{"name":"intake"}}\n\n{"type":"serp","data":{}}\n';
  assert.deepEqual(parseEvents(text).map((e) => e.type), ["stage", "serp"]);
});

import { clamp, ease, shift, wheelPixels } from "../dist/motion.js";

test("easing approaches the target, never overshoots and settles exactly", () => {
  let value = 0;
  for (let i = 0; i < 400; i += 1) value = ease(value, 1000, 1 / 60, 8);
  assert.equal(value, 1000);
  assert.ok(ease(0, 100, 1 / 60, 8) > 0 && ease(0, 100, 1 / 60, 8) < 100);
  assert.equal(ease(5, 5, 0.016, 8), 5);
});

test("a layer at the middle of the screen does not move and far ones are capped", () => {
  assert.equal(shift(1450, 1000, 900, 0.1), 0);
  assert.equal(shift(5000, 0, 900, 0.1), 48);
  assert.equal(shift(-5000, 0, 900, 0.1), -48);
  assert.equal(clamp(5, 0, 3), 3);
});

test("wheel deltas are normalised from pixels, lines and pages", () => {
  assert.equal(wheelPixels(100, 0, 900), 100);
  assert.equal(wheelPixels(3, 1, 900), 96);
  assert.equal(wheelPixels(1, 2, 900), 900);
});
