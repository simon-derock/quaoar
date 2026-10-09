// pure functions: events and cards in, plain text and rows out; the dom code only places them
export type Status = "consistent" | "inconsistent" | "unverified" | "not_applicable";

export interface Evidence {
  url: string;
  title: string;
  search_id: string | null;
  engine: string;
}

export interface Signal {
  rule: string;
  status: Status;
  text: string;
  evidence: Evidence[];
}

export interface Card {
  company: string;
  consistent: number;
  inconsistent: number;
  unverified: number;
  signals: Signal[];
  context?: Signal[];
  disclaimer: string;
}

export interface QEvent {
  type: string;
  data: Record<string, unknown>;
}

export const MARKS: Record<Status, string> = {
  consistent: "checks out",
  inconsistent: "doesn't match",
  unverified: "couldn't find",
  not_applicable: "not applicable",
};

// control characters and bidi marks never reach the page, whatever the server sends
// eslint-disable-next-line no-control-regex
const UNSAFE = /[\u0000-\u0008\u000b-\u001f\u007f-\u009f‪-‮⁦-⁩​-‍﻿]/g;

export function clean(text: string): string {
  return text.replace(UNSAFE, "");
}

export function formatEvent(event: QEvent): string | null {
  const d = event.data;
  switch (event.type) {
    case "serp":
      return `  search ${String(d["engine"])} · ${String(d["credits"])} cr · ${String(d["source"])} · ${String(d["latency_ms"])} ms`;
    case "llm": {
      const cost = d["cached"] === true ? "cache" : `${String(d["tokens_in"])}+${String(d["tokens_out"])} tok`;
      return `  read ${String(d["task"])} · ${cost} · ${String(d["latency_ms"])} ms`;
    }
    case "agent": {
      const flag = d["flagged"] ? ` [flagged ${clean(String(d["flagged"]))}]` : "";
      return `  agent ${clean(String(d["tool"]))} "${clean(String(d["terms"]))}" · ${String(d["hits"])} hits · ${String(d["credits"])} cr · ${clean(String(d["why"])).slice(0, 110)}${flag}`;
    }
    case "stage": {
      const name = clean(String(d["name"] ?? "stage"));
      // show the one detail that makes a stage readable: the subject, the cutoff date, or the timing
      const extra = d["subject"] ?? d["date"] ?? (d["ms"] === undefined ? undefined : `${String(d["ms"])} ms`);
      return extra === undefined ? name : `${name} · ${clean(String(extra))}`;
    }
    default:
      return null;
  }
}

export function headline(card: Card): string {
  const total = card.consistent + card.inconsistent + card.unverified;
  return `${card.consistent} of ${total} check out · ${card.inconsistent} don't match · ${card.unverified} couldn't find`;
}

// only https links are ever offered as links
export function safeLink(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

export type LineKind = "stage" | "serp" | "llm" | "agent";

// the terminal colours a line by what produced it
export function lineKind(event: QEvent): LineKind {
  return event.type === "serp" || event.type === "llm" || event.type === "agent" ? event.type : "stage";
}

// a proof chip shows the site it points to, not the whole address
export function host(url: string): string {
  const link = safeLink(url);
  return link === null ? "" : new URL(link).hostname.replace(/^www\./, "");
}

export function shares(card: Card): { ok: number; bad: number; none: number } {
  const total = card.consistent + card.inconsistent + card.unverified;
  const pct = (n: number): number => (total === 0 ? 0 : (n / total) * 100);
  return { ok: pct(card.consistent), bad: pct(card.inconsistent), none: pct(card.unverified) };
}

const LABELS: Record<string, string> = {
  trafiksol: "Trafiksol",
  aelea: "Aelea Commodities",
  "indian-emulsifier": "Indian Emulsifier",
  "tbi-corn": "TBI Corn",
  teamtech: "Teamtech Formwork",
};

const BLURBS: Record<string, string> = {
  trafiksol: "The case that made the news",
  aelea: "Control · no known problem",
  "indian-emulsifier": "Control · no known problem",
  "tbi-corn": "Control · no known problem",
  teamtech: "Unseen prospectus · no ground truth",
};

export function caseLabel(name: string): string {
  return LABELS[name] ?? name;
}

export function caseBlurb(name: string): string {
  return BLURBS[name] ?? "Recorded case";
}

// a replay bundle's events file has one json event per line
export function parseEvents(text: string): QEvent[] {
  return text
    .split("\n")
    .filter((line) => line.trim() !== "")
    .map((line) => JSON.parse(line) as QEvent);
}

export interface Row {
  kind: LineKind;
  label: string;
  text: string;
  meta: string;
  note: string;
}

const str = (value: unknown): string => clean(String(value ?? ""));

// the terminal shows one event as aligned columns: what ran, on what, and what it cost
export function rowParts(event: QEvent): Row | null {
  const d = event.data;
  switch (event.type) {
    case "serp":
      return { kind: "serp", label: "search", text: str(d["engine"]), meta: `${str(d["credits"])} cr · ${str(d["source"])} · ${str(d["latency_ms"])} ms`, note: "" };
    case "llm":
      return { kind: "llm", label: "read", text: str(d["task"]), meta: d["cached"] === true ? "cache" : `${str(d["tokens_in"])}+${str(d["tokens_out"])} tok`, note: "" };
    case "agent": {
      const flag = d["flagged"] ? ` · flagged ${str(d["flagged"])}` : "";
      return { kind: "agent", label: "agent", text: `${str(d["tool"])} "${str(d["terms"])}"`, meta: `${str(d["hits"])} hits · ${str(d["credits"])} cr${flag}`, note: str(d["why"]).slice(0, 110) };
    }
    case "stage": {
      const detail = d["subject"] ?? d["date"];
      const ms = d["ms"] === undefined ? "" : `${str(d["ms"])} ms`;
      return { kind: "stage", label: str(d["name"] ?? "stage"), text: detail === undefined ? "" : str(detail), meta: ms, note: "" };
    }
    default:
      return null;
  }
}
