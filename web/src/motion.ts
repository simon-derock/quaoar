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
