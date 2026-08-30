import { useEffect, useState } from "react";

const DISMISS_KEY = "psa-synthetic-notice-dismissed:v1";

export function SyntheticBanner() {
  const [visible, setVisible] = useState(false);
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    try {
      if (sessionStorage.getItem(DISMISS_KEY) === "1") {
        return;
      }
    } catch {
      // sessionStorage unavailable
    }

    setVisible(true);
    const frame = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  function dismiss() {
    setEntered(false);
    window.setTimeout(() => {
      setVisible(false);
      try {
        sessionStorage.setItem(DISMISS_KEY, "1");
      } catch {
        // ignore
      }
    }, 180);
  }

  if (!visible) {
    return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed right-4 top-4 z-50 max-w-[min(22rem,calc(100vw-2rem))] rounded-[10px] border border-white/12 bg-psa-graphite/95 px-4 py-3 shadow-[0_12px_40px_rgba(0,0,0,0.45)] backdrop-blur-sm transition-all duration-200 ease-out motion-reduce:transition-none ${
        entered ? "translate-y-0 opacity-100" : "-translate-y-2 opacity-0"
      }`}
    >
      <div className="flex items-start gap-3">
        <p className="flex-1 text-[11px] leading-relaxed text-psa-chalk">
          <span className="font-medium tracking-[0.12em] text-psa-amber">
            SYNTHETIC DATA
          </span>
          <span className="mx-1.5 text-psa-steel">·</span>
          All vessel, container, yard, and timing values are demo fixtures for Tuas
          terminal recovery operations.
        </p>
        <button
          type="button"
          onClick={dismiss}
          className="psa-btn-ghost -mr-1 shrink-0 px-2 py-1 text-[10px] text-psa-steel"
          aria-label="Dismiss synthetic data notice"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
