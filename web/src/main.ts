// the page: plays a recorded scan from the api into a terminal and a card, and answers beginner questions
import { MARKS, caseBlurb, caseLabel, clean, formatEvent, headline, host, lineKind, safeLink, shares, titleCase } from "./render.js";
import { startScroll } from "./scroll.js";
import type { Card, QEvent, Signal } from "./render.js";

declare global {
  interface Window {
    QUAOAR_API?: string;
  }
}

const api = (window.QUAOAR_API ?? "").replace(/\/$/, "");
const QUESTIONS = ["What is an SME IPO?", "Where do I get a prospectus?", "Is this IPO safe?", "What does “couldn't find” mean?"];
let current: EventSource | null = null;

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (node === null) throw new Error(`missing #${id}`);
  return node as T;
}

function cursor(): HTMLElement {
  const existing = document.querySelector<HTMLElement>("#terminal .cursor");
  if (existing !== null) return existing;
  const node = document.createElement("span");
  node.className = "cursor";
  return node;
}

function line(text: string, kind: string): void {
  const terminal = el<HTMLPreElement>("terminal");
  const row = document.createElement("span");
  row.className = `l k-${kind}`;
  if (kind === "cmd") {
    const prompt = document.createElement("b");
    prompt.textContent = "$ ";
    row.append(prompt, document.createTextNode(text));
  } else {
    row.textContent = text;
  }
  terminal.append(row, cursor());
  terminal.scrollTop = terminal.scrollHeight;
}

function row(signal: Signal): HTMLElement {
  const item = document.createElement("li");
  item.className = signal.status;
  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = MARKS[signal.status];
  item.append(tag, document.createTextNode(clean(signal.text)));
  const proof = signal.evidence[0];
  const link = proof === undefined ? null : safeLink(proof.url);
  if (proof !== undefined && link !== null) {
    const a = document.createElement("a");
    a.className = "proof";
    a.href = link;
    a.rel = "noopener noreferrer";
    a.target = "_blank";
    a.textContent = `${host(link)} ↗`;
    item.append(a);
  }
  return item;
}

function showCard(card: Card): void {
  el("company").textContent = titleCase(clean(card.company));
  el("headline").textContent = headline(card);
  const list = el("signals");
  const rows = card.signals.map(row);
  rows.forEach((item, index) => item.style.setProperty("animation-delay", `${index * 70}ms`));
  list.replaceChildren(...rows);
  el("context").textContent = (card.context ?? []).map((note) => clean(note.text)).join(" ");
  el("disclaimer").textContent = card.disclaimer;
  const part = shares(card);
  for (const [name, value] of Object.entries(part)) {
    const bar = document.querySelector<HTMLElement>(`#meter .${name}`);
    if (bar !== null) bar.style.setProperty("width", `${value}%`);
  }
}

function reset(name: string): void {
  current?.close();
  el<HTMLPreElement>("terminal").replaceChildren();
  el("signals").replaceChildren();
  el("headline").textContent = "";
  el("context").textContent = "";
  el("disclaimer").textContent = "";
  el("blurb").textContent = caseBlurb(name);
  el("company").textContent = caseLabel(name);
  document.querySelectorAll<HTMLElement>("#meter i").forEach((bar) => bar.style.setProperty("width", "0"));
  document.querySelectorAll<HTMLButtonElement>("#cases button").forEach((tab) => {
    tab.setAttribute("aria-selected", String(tab.dataset["case"] === name));
  });
}

function play(name: string): void {
  reset(name);
  line(`quaoar replay ${name}`, "cmd");
  const source = new EventSource(`${api}/api/scan/stream?case=${encodeURIComponent(name)}`);
  current = source;
  source.addEventListener("event", (message) => {
    const event = JSON.parse((message as MessageEvent<string>).data) as QEvent;
    const text = formatEvent(event);
    if (text !== null) line(text, lineKind(event));
  });
  source.addEventListener("card", (message) => {
    showCard(JSON.parse((message as MessageEvent<string>).data) as Card);
  });
  source.addEventListener("done", () => source.close());
  source.onerror = () => {
    line("connection closed", "stage");
    source.close();
  };
}

function tabs(names: string[]): void {
  const bar = el("cases");
  bar.replaceChildren(
    ...names.map((name) => {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.role = "tab";
      tab.dataset["case"] = name;
      tab.textContent = caseLabel(name);
      tab.addEventListener("click", () => play(name));
      return tab;
    }),
  );
}

async function start(): Promise<void> {
  const response = await fetch(`${api}/api/cases`);
  const names = (await response.json()) as string[];
  const ordered = ["trafiksol", ...names.filter((name) => name !== "trafiksol")];
  tabs(ordered);
  let selected = ordered[0] ?? "trafiksol";
  el("run").addEventListener("click", () => {
    const tab = document.querySelector<HTMLElement>('#cases [aria-selected="true"]');
    selected = tab?.dataset["case"] ?? selected;
    play(selected);
  });
  play(selected);
}

function bubble(text: string, who: "me" | "bot"): void {
  const item = document.createElement("li");
  item.className = who;
  item.textContent = text;
  const thread = el("thread");
  thread.append(item);
  thread.scrollTop = thread.scrollHeight;
}

async function ask(question: string, shown: boolean): Promise<void> {
  if (shown) bubble(question, "me");
  try {
    const response = await fetch(`${api}/api/ask?q=${encodeURIComponent(question)}`);
    const body = (await response.json()) as { answer?: string };
    bubble(clean(body.answer ?? "Something went wrong. Try again."), "bot");
  } catch {
    bubble("Couldn't reach the server. It may be waking up; try again in a minute.", "bot");
  }
}

function chat(): void {
  const chips = el("chips");
  chips.replaceChildren(
    ...QUESTIONS.map((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.textContent = text;
      chip.addEventListener("click", () => void ask(text, true));
      return chip;
    }),
  );
  const input = el<HTMLInputElement>("question");
  el("ask-form").addEventListener("submit", (submit) => {
    submit.preventDefault();
    const text = input.value.trim();
    if (text === "") return;
    input.value = "";
    void ask(text, true);
  });
}

function reveal(): void {
  const nodes = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    nodes.forEach((node) => node.classList.add("in"));
    return;
  }
  const watcher = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          watcher.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.12 },
  );
  nodes.forEach((node) => watcher.observe(node));
}

reveal();
startScroll();
chat();
start().catch(() => line("couldn't reach the api; it may be waking up, try again in a minute", "stage"));
