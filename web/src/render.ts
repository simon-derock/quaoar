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
    case "stage":
      return clean(String(d["name"] ?? "stage"));
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
