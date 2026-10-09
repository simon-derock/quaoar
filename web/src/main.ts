// the page: plays a recorded scan from the api into a terminal and a card, and answers beginner questions
import { MARKS, caseBlurb, caseLabel, clean, headline, host, parseEvents, rowParts, safeLink, shares } from "./render.js";
import { startScroll } from "./scroll.js";
import { storyFrame } from "./story.js";
import { deviceFrame } from "./device.js";
import type { Card, QEvent, Signal } from "./render.js";

declare global {
  interface Window {
    QUAOAR_API?: string;
  }
}

const api = (window.QUAOAR_API ?? "").replace(/\/$/, "");
const QUESTIONS = ["What is an SME IPO?", "Where do I get a prospectus?", "Is this IPO safe?", "What does “couldn't find” mean?"];
const STEP_MS = 95;
let current: EventSource | null = null;
let run = 0;

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

function cell(className: string, text: string): HTMLSpanElement {
  const span = document.createElement("span");
  span.className = className;
  span.textContent = text;
  return span;
}

function append(row: HTMLElement): void {
  const terminal = el("terminal");
  terminal.append(row, cursor());
  terminal.scrollTop = terminal.scrollHeight;
}

function command(text: string): void {
  const row = document.createElement("div");
  row.className = "r cmd";
  row.append(cell("lb", "$"), cell("tx", text));
  append(row);
}

function show(event: QEvent): void {
  const parts = rowParts(event);
  if (parts === null) return;
  const row = document.createElement("div");
  row.className = `r ${parts.kind}`;
  row.append(cell("lb", parts.label), cell("tx", parts.text), cell("mt", parts.meta));
  if (parts.note !== "") row.append(cell("nt", parts.note));
  append(row);
}

function notice(text: string): void {
  const row = document.createElement("div");
  row.className = "r";
  row.append(cell("lb", ""), cell("tx", text));
  append(row);
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
  el("company").textContent = clean(card.company);
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
  run += 1;
  el("terminal").replaceChildren();
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


// plays a bundle shipped with the page at a steady pace; no network wait, so it never stalls
async function playStatic(name: string, mine: number): Promise<boolean> {
  try {
    const [events, card] = await Promise.all([
      fetch(`replays/${name}/events.jsonl`).then((r) => (r.ok ? r.text() : Promise.reject(new Error("missing")))),
      fetch(`replays/${name}/card.json`).then((r) => (r.ok ? (r.json() as Promise<Card>) : Promise.reject(new Error("missing")))),
    ]);
    const queue = parseEvents(events);
    let index = 0;
    const tick = (): void => {
      if (mine !== run) return;
      const event = queue[index];
      if (event === undefined) {
        showCard(card);
        return;
      }
      show(event);
      index += 1;
      window.setTimeout(tick, STEP_MS);
    };
    tick();
    return true;
  } catch {
    return false;
  }
}

function playStream(name: string): void {
  const source = new EventSource(`${api}/api/scan/stream?case=${encodeURIComponent(name)}`);
  current = source;
  source.addEventListener("event", (message) => show(JSON.parse((message as MessageEvent<string>).data) as QEvent));
  source.addEventListener("card", (message) => showCard(JSON.parse((message as MessageEvent<string>).data) as Card));
  source.addEventListener("done", () => source.close());
  source.onerror = () => {
    notice("connection closed");
    source.close();
  };
}

function play(name: string): void {
  reset(name);
  const mine = run;
  command(`quaoar replay ${name}`);
  void playStatic(name, mine).then((ok) => {
    if (!ok && mine === run) playStream(name);
  });
}

async function caseNames(): Promise<string[]> {
  try {
    const local = await fetch("replays/index.json");
    if (local.ok) return (await local.json()) as string[];
  } catch {
    // fall through to the api
  }
  const response = await fetch(`${api}/api/cases`);
  return (await response.json()) as string[];
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

let selected = "trafiksol";

async function start(): Promise<void> {
  const names = await caseNames();
  const ordered = ["trafiksol", ...names.filter((name) => name !== "trafiksol")];
  tabs(ordered);
  selected = ordered[0] ?? selected;
  el("run").addEventListener("click", () => {
    const tab = document.querySelector<HTMLElement>('#cases [aria-selected="true"]');
    selected = tab?.dataset["case"] ?? selected;
    play(selected);
  });
}

const loaded = start();

// the first case plays when the laptop has opened, so the visitor sees it run
function openFirst(): void {
  void loaded.then(() => play(selected)).catch(() => notice("Couldn't load the recorded cases. Reload the page to try again."));
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

// one load sequence: the hero and the product arrive in order, 90 ms apart
function arrive(): void {
  document.querySelectorAll<HTMLElement>(".enter").forEach((node, index) => node.style.setProperty("--d", `${index * 90}ms`));
  const go = (): void => document.body.classList.add("ready");
  void document.fonts.ready.then(() => requestAnimationFrame(go));
  window.setTimeout(go, 1200);
}

// the install line copies with one click and says so
function copier(): void {
  const button = el<HTMLButtonElement>("copy");
  button.addEventListener("click", () => {
    void navigator.clipboard.writeText(el("install-cmd").textContent ?? "").then(() => {
      button.textContent = "Copied";
      button.classList.add("done");
      window.setTimeout(() => {
        button.textContent = "Copy";
        button.classList.remove("done");
      }, 1600);
    });
  });
}

arrive();
copier();
startScroll([deviceFrame(openFirst), storyFrame()]);
chat();
