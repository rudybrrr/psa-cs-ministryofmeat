import { useEffect, useRef } from "react";
import gsap from "gsap";

import { motionEnabled } from "../lib/useReducedMotion";

export function useChapterTransition(chapterKey: string) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!motionEnabled() || !ref.current) return;
    const node = ref.current;
    gsap.fromTo(
      node,
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.22, ease: "power2.out" },
    );
  }, [chapterKey]);

  return ref;
}

export function useAuthorityGatePulse(active: boolean) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!motionEnabled() || !ref.current || !active) return;
    const tween = gsap.fromTo(
      ref.current,
      { boxShadow: "0 0 0 0 rgba(245, 158, 11, 0.35)" },
      {
        boxShadow: "0 0 0 6px rgba(245, 158, 11, 0)",
        duration: 0.55,
        ease: "power2.out",
      },
    );
    return () => {
      tween.kill();
    };
  }, [active]);

  return ref;
}

export function useKpiValuePulse(value: string) {
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (!motionEnabled() || !ref.current) return;
    gsap.fromTo(
      ref.current,
      { scale: 1.04, color: "var(--color-psa-signal)" },
      { scale: 1, color: "var(--color-psa-snow)", duration: 0.35, ease: "power2.out" },
    );
  }, [value]);

  return ref;
}
