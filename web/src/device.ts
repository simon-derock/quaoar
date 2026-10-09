// the laptop: its lid opens and it comes forward as the intro scrolls; the console on its screen starts once it is open
import { phase } from "./motion.js";

const CLOSED_DEG = -64;
const BASE_WIDTH = 1300;

export function deviceFrame(onOpen: () => void): (scroll: number) => void {
  const intro = document.getElementById("product");
  const device = document.getElementById("device");
  const copy = document.getElementById("introCopy");
  const lid = device?.querySelector<HTMLElement>(".lid") ?? null;
  if (intro === null || device === null || copy === null || lid === null) return () => undefined;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let opened = false;
  let last = -1;

  const open = (): void => {
    if (!opened) {
      opened = true;
      onOpen();
    }
  };

  return (scroll: number) => {
    // phones and reduced motion get an open laptop that doesn't move
    if (still || window.innerWidth <= 980) {
      open();
      return;
    }
    const travel = intro.offsetHeight - window.innerHeight;
    const p = Math.min(1, Math.max(0, (scroll - intro.offsetTop) / Math.max(1, travel)));
    if (p === last) return;
    last = p;
    const fit = Math.min((0.9 * window.innerWidth) / BASE_WIDTH, (0.8 * window.innerHeight) / (lid.offsetHeight + 22));
    const opening = phase(p, 0, 0.42);
    const fade = 1 - phase(p, 0.04, 0.3);
    device.style.setProperty("--lid", `${(CLOSED_DEG * (1 - opening)).toFixed(2)}deg`);
    device.style.setProperty("--rise", `${((1 - phase(p, 0, 0.5)) * window.innerHeight * 0.16).toFixed(1)}px`);
    device.style.setProperty("--scale", (fit * (0.72 + 0.28 * phase(p, 0.3, 0.9))).toFixed(4));
    device.style.setProperty("--cap", phase(p, 0.85, 1).toFixed(3));
    copy.style.setProperty("--copy", fade.toFixed(3));
    copy.style.setProperty("--copy-events", fade < 0.3 ? "none" : "auto");
    if (opening > 0.55) open();
  };
}
