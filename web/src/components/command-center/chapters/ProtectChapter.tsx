import type { AgentRun } from "../../../api/types";
import type { CargoSafetyHistory, CargoSafetyReview } from "../../../api/types";
import { useEffect, useRef } from "react";
import gsap from "gsap";

import { motionEnabled } from "../../../lib/useReducedMotion";
import { ChapterFrame, ComparisonColumn } from "./ChapterFrame";

export function ProtectChapter({
  run,
  reviews,
  histories,
  loading,
  onCreateCanonical,
  evidenceOnly = false,
  quiet = false,
}: {
  run: AgentRun | null;
  reviews: CargoSafetyReview[];
  histories: CargoSafetyHistory[];
  loading: boolean;
  onCreateCanonical(): void;
  evidenceOnly?: boolean;
  quiet?: boolean;
}) {
  const history = histories[0];
  const assessment = history?.assessment;
  const policy = history?.policy_result;
  const note = history?.note;
  const finaleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!motionEnabled() || !finaleRef.current || !policy?.automation_blocked) return;
    const items = finaleRef.current.querySelectorAll("[data-protect-step]");
    gsap.fromTo(
      items,
      { opacity: 0, y: 8 },
      { opacity: 1, y: 0, duration: 0.24, stagger: 0.12, ease: "power2.out" },
    );
  }, [policy?.automation_blocked, assessment?.result]);

  return (
    <ChapterFrame
      label="Chapter 7 · Protect"
      title="Semantic detection — deterministic safety owns automation"
      quiet={quiet}
    >
      <p className="max-w-2xl !pt-0 text-sm leading-relaxed text-psa-chalk">
        Cargo safety separates semantic inconsistency detection from deterministic
        automation policy. A blocked escalation is a controlled successful outcome —
        not an application failure.
      </p>

      {reviews.length === 0 && !evidenceOnly ? (
        <button
          type="button"
          disabled={loading}
          onClick={onCreateCanonical}
          className="psa-btn-primary px-4 py-2.5 text-xs"
        >
          Record SYN-CNT-010 safety evidence
        </button>
      ) : null}

      {reviews.length > 0 && history?.review ? (
        <p className="text-xs text-psa-chalk">Review: {history.review.state}</p>
      ) : null}

      {history ? (
        <div ref={finaleRef} className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <ComparisonColumn heading="Structured manifest" tone="protect">
              <p className="font-medium">Trusted declaration source</p>
              <p>
                DG{" "}
                {assessment ? String(assessment.structured_dangerous_goods) : "pending"} · UN{" "}
                {assessment?.structured_un_number ?? "—"} · commodity{" "}
                {assessment?.structured_commodity ?? "—"}
              </p>
            </ComparisonColumn>
            <ComparisonColumn heading="Untrusted handling note" tone="protect">
              <p>{note?.text ?? "pending"}</p>
              <p className="text-psa-data-ink/60">({note?.source ?? "—"})</p>
            </ComparisonColumn>
          </div>

          <div
            data-protect-step
            className="border-l-2 border-psa-coral/60 pl-4"
          >
            <p className="psa-meta text-psa-coral">Semantic assessment</p>
            <p className="psa-mono mt-2 text-lg text-psa-snow">
              {assessment?.result ?? "pending"}
            </p>
            {assessment ? (
              <>
                <p className="mt-2 text-xs text-psa-chalk">
                  Evidence: {assessment.evidence_excerpt ?? "—"}
                </p>
                <p className="mt-1 text-xs text-psa-chalk">
                  Explanation: {assessment.explanation}
                </p>
              </>
            ) : (
              <p className="mt-2 text-xs text-psa-chalk">Semantic result: pending</p>
            )}
          </div>

          <div data-protect-step>
            <p className="psa-meta">Deterministic safety policy</p>
            <p className="mt-2 text-sm font-medium text-psa-snow">
              {policy ? policy.disposition.replaceAll("_", " ") : "pending"}
            </p>
            <p className="mt-1 font-mono text-sm text-psa-coral">AUTOMATION BLOCKED</p>
            <p className="mt-2 text-sm text-psa-chalk">
              {policy
                ? `Deterministic policy: ${policy.disposition} · automation blocked ${String(policy.automation_blocked)}`
                : "Deterministic policy: pending"}
            </p>
            {policy ? <p className="mt-1 text-xs text-psa-steel">Policy reason: {policy.reason}</p> : null}
            <p className="mt-3 text-sm font-medium text-psa-amber">
              HUMAN DG REVIEW REQUIRED
            </p>
          </div>
        </div>
      ) : null}

      {run?.state === "ESCALATED" ? (
        <div className="border-l-2 border-psa-coral/50 pl-4">
          <p className="psa-meta">Final agent state</p>
          <p className="psa-mono mt-2 text-xl text-psa-coral">{run.state}</p>
          {run.escalation_reason ? (
            <p className="mt-2 text-sm text-psa-coral">
              Escalated: {run.escalation_reason}
            </p>
          ) : null}
          <p className="mt-1 text-sm text-psa-chalk">
            Controlled escalation — safety review required before automation may proceed.
          </p>
        </div>
      ) : null}
    </ChapterFrame>
  );
}
