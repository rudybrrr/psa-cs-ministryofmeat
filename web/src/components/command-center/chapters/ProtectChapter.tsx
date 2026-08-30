import type { AgentRun } from "../../../api/types";
import type { CargoSafetyHistory, CargoSafetyReview } from "../../../api/types";
import { ChapterFrame, ComparisonColumn } from "./ChapterFrame";

export function ProtectChapter({
  run,
  reviews,
  histories,
  loading,
  onCreateCanonical,
}: {
  run: AgentRun | null;
  reviews: CargoSafetyReview[];
  histories: CargoSafetyHistory[];
  loading: boolean;
  onCreateCanonical(): void;
}) {
  const history = histories[0];
  const assessment = history?.assessment;
  const policy = history?.policy_result;
  const note = history?.note;

  return (
    <ChapterFrame
      label="Chapter 7 · Protect"
      title="Semantic detection — deterministic safety owns automation"
    >
      <p className="max-w-2xl text-sm leading-relaxed text-psa-chalk">
        Cargo safety separates semantic inconsistency detection from deterministic
        automation policy. A blocked escalation is a controlled successful outcome —
        not an application failure.
      </p>

      {reviews.length === 0 ? (
        <button
          type="button"
          disabled={loading}
          onClick={onCreateCanonical}
          className="psa-btn-primary px-4 py-2.5 text-xs"
        >
          Record SYN-CNT-010 safety evidence
        </button>
      ) : null}

      {history ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <ComparisonColumn heading="Structured manifest">
            <p>Trusted declaration source</p>
            <p>
              DG{" "}
              {assessment ? String(assessment.structured_dangerous_goods) : "pending"} ·
              UN {assessment?.structured_un_number ?? "—"} · commodity{" "}
              {assessment?.structured_commodity ?? "—"}
            </p>
          </ComparisonColumn>
          <ComparisonColumn heading="Untrusted handling note">
            <p>{note?.text ?? "pending"}</p>
            <p className="text-psa-steel">({note?.source ?? "—"})</p>
          </ComparisonColumn>
        </div>
      ) : null}

      {history ? (
        <>
          <p className="text-xs text-psa-chalk">
            Review: {history.review.state}
          </p>

          <div className="rounded-[8px] border border-psa-coral/40 bg-psa-coral/10 px-4 py-4">
            <p className="psa-label text-psa-coral">Semantic assessment</p>
            <p className="mt-2 font-mono text-lg text-psa-snow">
              {assessment?.result ?? "pending"}
            </p>
            {!assessment ? (
              <p className="mt-2 text-xs text-psa-chalk">Semantic result: pending</p>
            ) : null}
            {assessment ? (
              <>
                <p className="mt-2 text-xs text-psa-chalk">
                  Evidence: {assessment.evidence_excerpt ?? "—"}
                </p>
                <p className="mt-1 text-xs text-psa-chalk">
                  Explanation: {assessment.explanation}
                </p>
              </>
            ) : null}
          </div>

          <div className="rounded-[8px] border border-psa-graphite bg-psa-graphite/20 px-4 py-4">
            <p className="psa-label">Deterministic safety policy</p>
            <p className="mt-2 text-sm font-medium text-psa-snow">
              {policy ? policy.disposition.replaceAll("_", " ") : "pending"}
            </p>
            <p className="mt-1 font-mono text-sm text-psa-coral">
              AUTOMATION BLOCKED
            </p>
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
        </>
      ) : null}

      {run?.state === "ESCALATED" ? (
        <div className="psa-surface-nested rounded-[8px] border border-psa-coral/30 px-4 py-4">
          <p className="psa-label">Final agent state</p>
          <p className="mt-2 font-mono text-xl text-psa-coral">{run.state}</p>
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
