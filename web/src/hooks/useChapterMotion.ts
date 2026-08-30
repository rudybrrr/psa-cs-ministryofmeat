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

function parseKpiNumericValue(value: string): { target: number; decimals: number } | null {
  if (value === "—" || value === "-" || value.trim() === "") return null;
  const target = Number(value);
  if (!Number.isFinite(target)) return null;
  const dotIndex = value.indexOf(".");
  const decimals = dotIndex >= 0 ? value.length - dotIndex - 1 : 0;
  return { target, decimals };
}

function formatKpiCount(value: number, decimals: number): string {
  if (decimals > 0) return value.toFixed(decimals);
  return String(Math.round(value));
}

function kpiCountStart(target: number): number {
  return target >= 1 ? 1 : 0;
}

function kpiCountDuration(target: number): number {
  return Math.min(1.35, 0.65 + Math.log10(Math.max(target, 1)) * 0.35);
}

export function useKpiCountUp(value: string) {
  const ref = useRef<HTMLParagraphElement>(null);
  const parsed = parseKpiNumericValue(value);
  const initialDisplay =
    parsed && motionEnabled()
      ? formatKpiCount(kpiCountStart(parsed.target), parsed.decimals)
      : value;

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const numeric = parseKpiNumericValue(value);
    if (!numeric) {
      node.textContent = value;
      return;
    }

    const { target, decimals } = numeric;
    if (!motionEnabled()) {
      node.textContent = formatKpiCount(target, decimals);
      return;
    }

    const start = kpiCountStart(target);
    const state = { current: start };
    node.textContent = formatKpiCount(start, decimals);

    const tween = gsap.to(state, {
      current: target,
      duration: kpiCountDuration(target),
      ease: "power2.out",
      onUpdate: () => {
        node.textContent = formatKpiCount(state.current, decimals);
      },
    });

    return () => {
      tween.kill();
    };
  }, [value]);

  return { ref, initialDisplay };
}
