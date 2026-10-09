// pure maths for the smooth scroll and the parallax; the dom code only applies the numbers

const MAX_SHIFT = 48;

// moves `current` toward `target`; the same rate gives the same feel at 60 and 144 frames per second
export function ease(current: number, target: number, seconds: number, rate: number): number {
  const next = current + (target - current) * (1 - Math.exp(-rate * seconds));
  return Math.abs(target - next) < 0.05 ? target : next;
}

export function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

// how far a layer sits from where it would be without parallax; depth 0 is none, 0.1 lags 10% behind the scroll
export function shift(centre: number, scroll: number, viewport: number, depth: number): number {
  return clamp((centre - scroll - viewport / 2) * depth, -MAX_SHIFT, MAX_SHIFT);
}

// wheel deltas arrive in pixels, lines or pages depending on the device
export function wheelPixels(delta: number, mode: number, viewport: number): number {
  if (mode === 1) return delta * 32;
  if (mode === 2) return delta * viewport;
  return delta;
}

// eases a 0..1 value in and out, for things already on screen that move
export function inOut(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

// how far along one step of a scroll-driven sequence is, from 0 before it starts to 1 after it ends
export function phase(progress: number, start: number, end: number): number {
  return inOut(clamp((progress - start) / (end - start), 0, 1));
}

export function typed(text: string, t: number): string {
  return text.slice(0, Math.round(text.length * clamp(t, 0, 1)));
}

export function countUp(from: number, to: number, t: number): number {
  return Math.round(from + (to - from) * clamp(t, 0, 1));
}
