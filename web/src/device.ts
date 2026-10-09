// the product shot: it waits below the headline and rises and grows into view as the intro scrolls,
// always sized to fit the window; the recorded case starts playing on it straight away
import { phase } from "./motion.js";

const TILT_DEG = 0;
const MARGIN_X = 96;
const MARGIN_Y = 150;

export function deviceFrame(onOpen: () => void): (scroll: number) => void {
  const intro = document.getElementById("product");
  const shot = document.getElementById("device");
  const copy = document.getElementById("introCopy");
  const pane = shot?.querySelector<HTMLElement>(".window") ?? null;
  if (intro === null || shot === null || copy === null || pane === null) return () => undefined;
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
    if (still || window.innerWidth <= 980) {
      open();
      return;
    }
    const travel = intro.offsetHeight - window.innerHeight;
    const p = Math.min(1, Math.max(0, (scroll - intro.offsetTop) / Math.max(1, travel)));
    if (p === last) return;
    last = p;
    // the whole window must fit with room for the header, so no edge is ever cut
    const fit = Math.min(1, (window.innerWidth - MARGIN_X) / pane.offsetWidth, (window.innerHeight - MARGIN_Y) / pane.offsetHeight);
    const flat = phase(p, 0, 0.6);
    shot.style.setProperty("--tilt", `${(TILT_DEG * (1 - flat)).toFixed(2)}deg`);
    shot.style.setProperty("--rise", `${((1 - flat) * window.innerHeight * 0.56 + 20).toFixed(1)}px`);
    shot.style.setProperty("--scale", (fit * (0.8 + 0.2 * flat)).toFixed(4));
    shot.style.setProperty("--halo", flat.toFixed(3));
    shot.style.setProperty("--cap", phase(p, 0.7, 0.95).toFixed(3));
    const fade = 1 - phase(p, 0.02, 0.32);
    copy.style.setProperty("--copy", fade.toFixed(3));
    copy.style.setProperty("--copy-events", fade < 0.3 ? "none" : "auto");
    open();
  };
}
