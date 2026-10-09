// ultra smooth scrolling and parallax: wheel input is eased, touch and keyboard stay native
import { clamp, ease, inOut, shift, wheelPixels } from "./motion.js";

const RATE = 14;

interface Tween {
  from: number;
  to: number;
  start: number;
  ms: number;
}

// a menu jump is a move between two known points, so it eases in and out over a time set by its distance
function jumpMs(distance: number): number {
  return clamp(Math.abs(distance) * 0.3, 450, 1000);
}

interface Layer {
  node: HTMLElement;
  centre: number;
  depth: number;
}

function innerScroller(start: EventTarget | null, down: boolean): boolean {
  // a pane that can still scroll in this direction keeps the wheel for itself
  let node = start instanceof HTMLElement ? start : null;
  while (node !== null && node !== document.body) {
    const style = getComputedStyle(node);
    const room = node.scrollHeight > node.clientHeight + 1;
    if (room && (style.overflowY === "auto" || style.overflowY === "scroll")) {
      const atEnd = down ? node.scrollTop + node.clientHeight >= node.scrollHeight - 1 : node.scrollTop <= 0;
      if (!atEnd) return true;
    }
    node = node.parentElement;
  }
  return false;
}

function layers(): Layer[] {
  const found: Layer[] = [];
  document.querySelectorAll<HTMLElement>("[data-depth]").forEach((node) => {
    node.style.removeProperty("--py");
    const box = node.getBoundingClientRect();
    found.push({ node, centre: box.top + window.scrollY + box.height / 2, depth: Number(node.dataset["depth"] ?? 0) });
  });
  return found;
}

type Hook = (scroll: number) => void;

export function startScroll(hooks: Hook[] = []): void {
  // a refresh always starts at the top unless the address names a section
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  if (window.location.hash === "") window.scrollTo(0, 0);
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const header = document.querySelector<HTMLElement>(".top");
  let items = layers();
  let current = window.scrollY;
  let target = current;
  let last = performance.now();
  let lastY = current;
  let tween: Tween | null = null;
  const limit = (): number => document.documentElement.scrollHeight - window.innerHeight;

  window.addEventListener(
    "wheel",
    (event) => {
      if (still || event.ctrlKey || event.deltaY === 0 || innerScroller(event.target, event.deltaY > 0)) return;
      event.preventDefault();
      tween = null;
      target = clamp(target + wheelPixels(event.deltaY, event.deltaMode, window.innerHeight), 0, limit());
    },
    { passive: false },
  );
  // keyboard, scrollbar and touch move the page natively: follow them instead of fighting them
  window.addEventListener("scroll", () => {
    if (Math.abs(window.scrollY - current) > 3) {
      current = window.scrollY;
      target = current;
    }
  });
  document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (event) => {
      const goal = document.querySelector<HTMLElement>(link.getAttribute("href") ?? "");
      if (goal === null || still) return;
      event.preventDefault();
      const to = clamp(goal.getBoundingClientRect().top + window.scrollY - 24, 0, limit());
      tween = { from: window.scrollY, to, start: performance.now(), ms: jumpMs(to - window.scrollY) };
    });
  });
  window.addEventListener("resize", () => {
    items = layers();
  });
  window.addEventListener("load", () => {
    items = layers();
  });

  const frame = (now: number): void => {
    const seconds = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (tween !== null) {
      const t = Math.min(1, (now - tween.start) / tween.ms);
      current = tween.from + (tween.to - tween.from) * inOut(t);
      target = current;
      window.scrollTo(0, current);
      if (t === 1) tween = null;
    } else if (!still && current !== target) {
      current = ease(current, target, seconds, RATE);
      window.scrollTo(0, current);
    }
    const y = window.scrollY;
    if (!still) for (const item of items) item.node.style.setProperty("--py", `${shift(item.centre, y, window.innerHeight, item.depth).toFixed(2)}px`);
    header?.classList.toggle("solid", y > 40);
    for (const hook of hooks) hook(y);
    if (y > lastY + 1 && y > 220) header?.classList.add("away");
    if (y < lastY - 1 || y <= 220) header?.classList.remove("away");
    lastY = y;
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
