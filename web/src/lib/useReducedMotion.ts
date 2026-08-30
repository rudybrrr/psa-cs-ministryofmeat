export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return true;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function motionEnabled(): boolean {
  return !import.meta.env.VITEST && !prefersReducedMotion();
}
