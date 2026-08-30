export function ResumePrompt({
  incidentId,
  loading,
  onResume,
  onStartFresh,
  onDismiss,
}: {
  incidentId: string;
  loading: boolean;
  onResume(): void;
  onStartFresh(): void;
  onDismiss(): void;
}) {
  return (
    <section
      role="status"
      className="psa-surface rounded-[10px] border border-psa-signal/30 px-5 py-4"
    >
      <p className="psa-label text-psa-signal">Saved session</p>
      <h2 className="mt-1 text-sm font-medium text-psa-snow">Resume current demo?</h2>
      <p className="mt-2 text-sm text-psa-fog">
        A persisted incident was found locally. Resume continues the same backend state —
        starting fresh creates a new canonical incident.
      </p>
      <p className="mt-2 font-mono text-[11px] text-psa-steel">{incidentId}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={onResume}
          className="psa-btn psa-btn-primary"
        >
          Resume current demo
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={onStartFresh}
          className="psa-btn psa-btn-secondary"
        >
          Start fresh demo
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={onDismiss}
          className="psa-btn psa-btn-ghost"
        >
          Dismiss
        </button>
      </div>
    </section>
  );
}
