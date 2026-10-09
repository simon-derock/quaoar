// the console: streams a recorded scan from the api and shows the terminal and the card
import { MARKS, clean, formatEvent, headline, safeLink } from "./render.js";
import type { Card, QEvent, Signal } from "./render.js";

declare global {
  interface Window {
    QUAOAR_API?: string;
  }
}

const api = (window.QUAOAR_API ?? "").replace(/\/$/, "");

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (node === null) throw new Error(`missing #${id}`);
  return node as T;
}

function line(text: string): void {
  const terminal = el<HTMLPreElement>("terminal");
  terminal.append(document.createTextNode(`${text}\n`));
  terminal.scrollTop = terminal.scrollHeight;
}

function showCard(card: Card): void {
  el("company").textContent = clean(card.company);
  el("headline").textContent = headline(card);
  const list = el("signals");
  list.replaceChildren(...card.signals.map(row));
  el("context").textContent = (card.context ?? []).map((note) => clean(note.text)).join(" ");
  el("disclaimer").textContent = card.disclaimer;
}

function row(signal: Signal): HTMLElement {
  const item = document.createElement("li");
  item.className = signal.status;
  const mark = document.createElement("strong");
  mark.textContent = MARKS[signal.status];
  const text = document.createElement("span");
  text.textContent = ` ${clean(signal.text)}`;
  item.append(mark, text);
  const proof = signal.evidence[0];
  const link = proof === undefined ? null : safeLink(proof.url);
  if (proof !== undefined && link !== null) {
    const a = document.createElement("a");
    a.href = link;
    a.rel = "noopener noreferrer";
    a.target = "_blank";
    a.textContent = "show proof";
    item.append(" ", a);
  }
  return item;
}

function play(caseName: string): void {
  el<HTMLPreElement>("terminal").textContent = "";
  el("signals").replaceChildren();
  el("headline").textContent = "";
  line(`$ quaoar replay ${caseName}`);
  const source = new EventSource(`${api}/api/scan/stream?case=${encodeURIComponent(caseName)}`);
  source.addEventListener("event", (message) => {
    const text = formatEvent(JSON.parse((message as MessageEvent<string>).data) as QEvent);
    if (text !== null) line(text);
  });
  source.addEventListener("card", (message) => {
    showCard(JSON.parse((message as MessageEvent<string>).data) as Card);
  });
  source.addEventListener("done", () => source.close());
  source.onerror = () => {
    line("connection closed");
    source.close();
  };
}

async function start(): Promise<void> {
  const select = el<HTMLSelectElement>("case");
  const response = await fetch(`${api}/api/cases`);
  const names = (await response.json()) as string[];
  select.replaceChildren(...names.map((name) => new Option(name, name)));
  select.addEventListener("change", () => play(select.value));
  el("run").addEventListener("click", () => play(select.value));
  const first = names[0];
  if (first !== undefined) play(first);
}

start().catch(() => line("couldn't reach the api; it may be waking up, try again in a minute"));
