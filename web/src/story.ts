// the scroll-driven sequence: one prospectus claim read, searched, compared and proved, using the real trafiksol evidence
import { countUp, phase, typed } from "./motion.js";

const QUERY = '"OASIS CORPCARE" (site:zaubacorp.com OR site:instafinancials.com OR site:tofler.in)';
const RATIO = 1770;

// each step's window inside the pinned scroll, 0 at the top of the section and 1 at its end
const STEPS: Record<string, [number, number]> = {
  a: [0, 0.1],
  scan: [0.04, 0.24],
  b: [0.2, 0.3],
  move: [0.28, 0.42],
  c: [0.38, 0.46],
  type: [0.44, 0.56],
  r1: [0.56, 0.61],
  r2: [0.6, 0.65],
  d: [0.66, 0.74],
  count: [0.7, 0.82],
  e: [0.84, 0.92],
};
const MARKS = [0.1, 0.3, 0.46, 0.66, 0.84];

export function storyFrame(): (scroll: number) => void {
  const section = document.getElementById("how");
  const scene = document.getElementById("scene");
  const query = document.getElementById("query");
  const ratio = document.getElementById("ratio");
  const steps = Array.from(document.querySelectorAll<HTMLElement>("#steps li"));
  if (section === null || scene === null || query === null || ratio === null) return () => undefined;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let last = -1;

  return (scroll: number) => {
    // phones and reduced motion see the finished state, with nothing pinned
    const flat = still || window.innerWidth <= 980;
    const top = section.offsetTop;
    const travel = section.offsetHeight - window.innerHeight;
    const p = flat ? 1 : Math.min(1, Math.max(0, (scroll - top) / Math.max(1, travel)));
    if (p === last) return;
    last = p;
    for (const [name, [start, end]] of Object.entries(STEPS)) scene.style.setProperty(`--${name}`, phase(p, start, end).toFixed(4));
    query.textContent = typed(QUERY, phase(p, ...STEPS["type"]!));
    ratio.textContent = countUp(1, RATIO, phase(p, ...STEPS["count"]!)).toLocaleString("en-IN");
    const reached = MARKS.filter((mark) => p >= mark).length - 1;
    steps.forEach((step, index) => step.classList.toggle("on", index === Math.max(0, reached)));
  };
}
