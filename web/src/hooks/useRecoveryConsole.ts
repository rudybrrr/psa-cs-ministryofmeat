import { useCallback, useMemo, useRef, useState } from "react";

import {
  approveCounter,
  approveRequest,
  evaluateTimeout,
  getCarrierCaseHistory,
  listCarrierCases,
  prepareCarrierRecovery as prepareCarrierRecoveryApi,
  rejectCounter,
  rejectRequest,
  sendCarrierRequest,
  simulateCarrierResponse,
} from "../api/carrierRecovery";
import { ApiError } from "../api/client";
import {
  getAuditEvents,
  getDecisions,
  getIncident,
} from "../api/client";
import {
  getCanonicalFixture,
  getScarcityEvaluation,
  triggerCanonicalScarcity,
} from "../api/scarcity";
import { createAgentRun, advanceAgentRun, getAgentRunHistory, listAgentRuns } from "../api/agentRuntime";
import { bootstrapDynamicYard, listAllocationRevisions, listExpediteCommitments, listReconsiderations, listTradeoffOptions, listTradeoffReviews, listYardForecasts, publishDischargeActive, selectTradeoff } from "../api/dynamicYard";
import { createCargoSafetyReview, evaluateCargoSafetyReview, getCargoSafetyHistory, listCargoSafetyReviews } from "../api/cargoSafety";
import { createCanonicalDemoAgentRun, fetchCanonicalReplayStage, initialCanonicalStageView } from "../api/canonicalReplay";
import type {
  AuditEvent,
  CanonicalIncidentFixture,
  CanonicalReplayStageView,
  CarrierRecoveryCase,
  CarrierRecoveryHistory,
  Decision,
  Incident,
  ScarcityEvaluationReport,
  AgentHistory, AgentRun, AllocationRevision, AllocationTradeoffOption, AllocationTradeoffReview, CargoSafetyHistory, CargoSafetyReview, ExpediteCommitment, ExpediteReconsiderationAssessment, YardForecastSnapshot,
} from "../api/types";
import type { CanonicalDemoRunId } from "../lib/canonicalDemo";
import {
  CARRIER_DEMO_TIMESTAMPS,
  demoRunById,
} from "../lib/canonicalDemo";
import {
  buildContainerRows,
  buildRecoverySummary,
  carrierCaseForConnection,
  latestSnapshot,
  latestAllocationRevision,
} from "../lib/recoverySelectors";

export interface RecoveryConsoleState {
  incident: Incident | null;
  fixture: CanonicalIncidentFixture | null;
  scarcityEvaluation: ScarcityEvaluationReport | null;
  decisions: Decision[];
  auditEvents: AuditEvent[];
  carrierCases: CarrierRecoveryCase[];
  selectedContainerId: string | null;
  selectedCarrierCaseId: string | null;
  selectedCaseHistory: CarrierRecoveryHistory | null;
  activeDemoRunId: CanonicalDemoRunId | null;
  loading: boolean;
  error: ApiError | null;
}

export interface MutationOutcome {
  ok: boolean;
  conflict: boolean;
  error: ApiError | null;
}

const SKIPPED_MUTATION: MutationOutcome = { ok: false, conflict: false, error: null };

async function loadIncidentBundle(incidentId: string) {
  const [
    incident,
    fixture,
    scarcityEvaluation,
    decisions,
    auditEvents,
    carrierCases,
    yardForecasts,
    allocationRevisions,
    expediteCommitments,
    reconsiderations,
    tradeoffReviews,
    tradeoffOptions,
    cargoSafetyReviews,
    agentRuns,
    canonicalStage,
  ] = await Promise.all([
    getIncident(incidentId),
    getCanonicalFixture(),
    getScarcityEvaluation(incidentId),
    getDecisions(incidentId),
    getAuditEvents(incidentId),
    listCarrierCases(incidentId),
    listYardForecasts(incidentId), listAllocationRevisions(incidentId), listExpediteCommitments(incidentId), listReconsiderations(incidentId), listTradeoffReviews(incidentId), listTradeoffOptions(incidentId), listCargoSafetyReviews(incidentId), listAgentRuns(incidentId),
    fetchCanonicalReplayStage(incidentId),
  ]);

  return {
    incident,
    fixture,
    scarcityEvaluation,
    decisions,
    auditEvents,
    carrierCases,
    yardForecasts, allocationRevisions, expediteCommitments, reconsiderations, tradeoffReviews, tradeoffOptions, cargoSafetyReviews, agentRuns, canonicalStage,
  };
}

export function useRecoveryConsole() {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [fixture, setFixture] = useState<CanonicalIncidentFixture | null>(null);
  const [scarcityEvaluation, setScarcityEvaluation] =
    useState<ScarcityEvaluationReport | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [carrierCases, setCarrierCases] = useState<CarrierRecoveryCase[]>([]);
  const [yardForecasts, setYardForecasts] = useState<YardForecastSnapshot[]>([]);
  const [allocationRevisions, setAllocationRevisions] = useState<AllocationRevision[]>([]);
  const [expediteCommitments, setExpediteCommitments] = useState<ExpediteCommitment[]>([]);
  const [reconsiderations, setReconsiderations] = useState<ExpediteReconsiderationAssessment[]>([]);
  const [tradeoffReviews, setTradeoffReviews] = useState<AllocationTradeoffReview[]>([]);
  const [tradeoffOptions, setTradeoffOptions] = useState<AllocationTradeoffOption[]>([]);
  const [cargoSafetyReviews, setCargoSafetyReviews] = useState<CargoSafetyReview[]>([]);
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([]);
  const [canonicalStage, setCanonicalStage] = useState<CanonicalReplayStageView | null>(null);

  const latestStateRef = useRef<{ incident: Incident | null; carrierCases: CarrierRecoveryCase[]; agentRuns: AgentRun[] }>({ incident: null, carrierCases: [], agentRuns: [] });
  latestStateRef.current = { incident, carrierCases, agentRuns };
  const [selectedAgentHistory, setSelectedAgentHistory] = useState<AgentHistory | null>(null);
  const [agentWaitHistory, setAgentWaitHistory] = useState<CarrierRecoveryHistory | null>(null);
  const [safetyHistories, setSafetyHistories] = useState<CargoSafetyHistory[]>([]);
  const [selectedContainerId, setSelectedContainerId] = useState<string | null>(
    null,
  );
  const [selectedCarrierCaseId, setSelectedCarrierCaseId] = useState<
    string | null
  >(null);
  const [selectedCaseHistory, setSelectedCaseHistory] =
    useState<CarrierRecoveryHistory | null>(null);
  const [activeDemoRunId, setActiveDemoRunId] =
    useState<CanonicalDemoRunId | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const recoverySummary = useMemo(() => {
    if (!fixture || !scarcityEvaluation) {
      return null;
    }
    return buildRecoverySummary(fixture, scarcityEvaluation);
  }, [fixture, scarcityEvaluation]);

  const containerRows = useMemo(() => {
    if (!fixture || !scarcityEvaluation) {
      return [];
    }
    return buildContainerRows(
      fixture,
      scarcityEvaluation,
      decisions,
      carrierCases,
      latestSnapshot(yardForecasts, "DISCHARGE_ACTIVE"),
      expediteCommitments,
      safetyHistories,
      latestAllocationRevision(allocationRevisions),
    );
  }, [fixture, scarcityEvaluation, decisions, carrierCases, yardForecasts, expediteCommitments, safetyHistories, allocationRevisions]);

  const selectedContainer = useMemo(
    () =>
      containerRows.find((row) => row.containerId === selectedContainerId) ??
      null,
    [containerRows, selectedContainerId],
  );

  const selectedCarrierCase = useMemo(() => {
    if (selectedCarrierCaseId) {
      return carrierCases.find((item) => item.id === selectedCarrierCaseId) ?? null;
    }
    if (!selectedContainer) {
      return null;
    }
    return carrierCaseForConnection(
      carrierCases,
      selectedContainer.connectionId,
    );
  }, [carrierCases, selectedCarrierCaseId, selectedContainer]);

  const applyBundle = useCallback(async (bundle: Awaited<ReturnType<typeof loadIncidentBundle>>) => {
    latestStateRef.current = { incident: bundle.incident, carrierCases: bundle.carrierCases, agentRuns: bundle.agentRuns };
    setIncident(bundle.incident);
    setFixture(bundle.fixture);
    setScarcityEvaluation(bundle.scarcityEvaluation);
    setDecisions(bundle.decisions);
    setAuditEvents(bundle.auditEvents);
    setCarrierCases(bundle.carrierCases);
    setYardForecasts(bundle.yardForecasts); setAllocationRevisions(bundle.allocationRevisions); setExpediteCommitments(bundle.expediteCommitments); setReconsiderations(bundle.reconsiderations); setTradeoffReviews(bundle.tradeoffReviews); setTradeoffOptions(bundle.tradeoffOptions); setCargoSafetyReviews(bundle.cargoSafetyReviews); setAgentRuns(bundle.agentRuns); setCanonicalStage(bundle.canonicalStage);
    const currentRun = bundle.agentRuns.at(-1);
    setSelectedAgentHistory(currentRun ? await getAgentRunHistory(currentRun.id) : null);
    setAgentWaitHistory(currentRun?.wait_subject_id && ["REQUEST_APPROVAL", "COUNTER_APPROVAL", "CARRIER_RESPONSE_OR_TIMEOUT"].includes(currentRun.wait_kind ?? "") ? await getCarrierCaseHistory(currentRun.wait_subject_id) : null);
    setSafetyHistories(await Promise.all(bundle.cargoSafetyReviews.map((review) => getCargoSafetyHistory(review.id))));
  }, []);

  const refresh = useCallback(async () => {
    // Read through the synchronous mirror so refresh works even when invoked
    // before React has flushed the state update that created the incident.
    const currentIncident = latestStateRef.current.incident;
    if (!currentIncident) {
      return;
    }
    const bundle = await loadIncidentBundle(currentIncident.id);
    await applyBundle(bundle);

    const activeCase =
      selectedCarrierCaseId &&
      bundle.carrierCases.find((item) => item.id === selectedCarrierCaseId);
    if (activeCase) {
      setSelectedCaseHistory(await getCarrierCaseHistory(activeCase.id));
    } else if (selectedContainerId) {
      const profile = bundle.fixture.profiles.find(
        (item) => item.container.id === selectedContainerId,
      );
      const matched = profile
        ? carrierCaseForConnection(
            bundle.carrierCases,
            profile.container.onward_connection.id,
          )
        : undefined;
      if (matched) {
        setSelectedCarrierCaseId(matched.id);
        setSelectedCaseHistory(await getCarrierCaseHistory(matched.id));
      }
    }
  }, [applyBundle, selectedCarrierCaseId, selectedContainerId]);

  const runMutation = useCallback(
    async (operation: () => Promise<void>): Promise<MutationOutcome> => {
      setLoading(true);
      setError(null);
      try {
        await operation();
        await refresh();
        return { ok: true, conflict: false, error: null };
      } catch (mutationError) {
        if (mutationError instanceof ApiError) {
          setError(mutationError);
          if (mutationError.status === 409) {
            await refresh();
            return { ok: false, conflict: true, error: mutationError };
          }
          return { ok: false, conflict: false, error: mutationError };
        }
        return { ok: false, conflict: false, error: new ApiError(0, String(mutationError)) };
      } finally {
        setLoading(false);
      }
    },
    [refresh],
  );

  const createCanonicalIncident = useCallback(async (): Promise<MutationOutcome> => {
    return runMutation(async () => {
      const trigger = await triggerCanonicalScarcity();
      const bundle = await loadIncidentBundle(trigger.incident_id);
      await applyBundle(bundle);
      setSelectedContainerId(null);
      setSelectedCarrierCaseId(null);
      setSelectedCaseHistory(null);
    });
  }, [applyBundle, runMutation]);

  const loadDemoRun = useCallback(
    async (runId: CanonicalDemoRunId) => {
      await runMutation(async () => {
        const run = demoRunById(runId);
        const trigger = await triggerCanonicalScarcity();
        const bundle = await loadIncidentBundle(trigger.incident_id);
        await applyBundle(bundle);
        setActiveDemoRunId(runId);

        const profile = bundle.fixture.profiles.find(
          (item) => item.container.onward_connection.id === run.connectionId,
        );
        if (profile) {
          setSelectedContainerId(profile.container.id);
        }
        setSelectedCarrierCaseId(null);
          setSelectedCaseHistory(null);
        });
      },
      [applyBundle, runMutation],
        );

  const selectContainer = useCallback(
    async (containerId: string) => {
      setSelectedContainerId(containerId);
      const profile = fixture?.profiles.find(
        (item) => item.container.id === containerId,
      );
      if (!profile || !incident) {
        setSelectedCarrierCaseId(null);
        setSelectedCaseHistory(null);
        return;
      }
      const matched = carrierCaseForConnection(
        carrierCases,
        profile.container.onward_connection.id,
      );
      if (matched) {
        setSelectedCarrierCaseId(matched.id);
        setSelectedCaseHistory(await getCarrierCaseHistory(matched.id));
      } else {
        setSelectedCarrierCaseId(null);
        setSelectedCaseHistory(null);
      }
    },
    [carrierCases, fixture, incident],
  );

  const prepareCarrierRecovery = useCallback(
    async (connectionId: string) => {
      if (!incident) {
        return;
      }
      await runMutation(async () => {
        const created = await prepareCarrierRecoveryApi(incident.id, {
          connection_id: connectionId,
          prepared_at: CARRIER_DEMO_TIMESTAMPS.preparedAt,
          requested_eta_pta: CARRIER_DEMO_TIMESTAMPS.requestedEtaPta,
          response_deadline: CARRIER_DEMO_TIMESTAMPS.responseDeadline,
        });
        setSelectedCarrierCaseId(created.id);
        setSelectedCaseHistory(await getCarrierCaseHistory(created.id));
      });
    },
    [incident, runMutation],
  );

  const withBinding = useCallback(
  async (
    caseId: string,
    subjectKind: "OUTBOUND_REQUEST" | "COUNTER_PROPOSAL",
    action: (binding: {
      proposal_decision_id: string;
      request_id?: string;
      carrier_response_id?: string;
      expected_payload_fingerprint: string;
    }) => Promise<void>,
  ) => {
    const history = await getCarrierCaseHistory(caseId);
    const binding = history.bindings.find(
      (item) => item.subject_kind === subjectKind,
    );
    if (!binding) {
      throw new Error(`No ${subjectKind} binding available`);
    }
    await action({
      proposal_decision_id: binding.proposal_decision_id,
      request_id:
        subjectKind === "OUTBOUND_REQUEST" ? binding.subject_id : undefined,
      carrier_response_id:
        subjectKind === "COUNTER_PROPOSAL" ? binding.subject_id : undefined,
      expected_payload_fingerprint: binding.payload_fingerprint,
    });
  },
  [],
);

  const resolveCarrierTarget = useCallback((): CarrierRecoveryCase | null => {
    const selected = selectedCarrierCase;
    return selected ?? latestStateRef.current.carrierCases.find((item) => item.connection_id === "SYN-CONN-JV2") ?? null;
  }, [selectedCarrierCase]);

  const approveRequestAction = useCallback(async (operatorId: string = "operator-console"): Promise<MutationOutcome> => {
    const targetCase = resolveCarrierTarget();
    if (!targetCase) {
      return SKIPPED_MUTATION;
    }
    return runMutation(async () => {
      await withBinding(
        targetCase.id,
        "OUTBOUND_REQUEST",
        async (binding) => {
          await approveRequest(targetCase.id, {
            proposal_decision_id: binding.proposal_decision_id,
            request_id: binding.request_id!,
            expected_payload_fingerprint: binding.expected_payload_fingerprint,
            operator_id: operatorId,
            status: "APPROVED",
          });
        },
      );
    });
  }, [resolveCarrierTarget, runMutation, withBinding]);

  const rejectRequestAction = useCallback(async (): Promise<MutationOutcome> => {
    const targetCase = resolveCarrierTarget();
    if (!targetCase) {
      return SKIPPED_MUTATION;
    }
    return runMutation(async () => {
      await withBinding(
        targetCase.id,
        "OUTBOUND_REQUEST",
        async (binding) => {
          await rejectRequest(targetCase.id, {
            proposal_decision_id: binding.proposal_decision_id,
            request_id: binding.request_id!,
            expected_payload_fingerprint: binding.expected_payload_fingerprint,
            operator_id: "operator-console",
          });
        },
      );
    });
  }, [resolveCarrierTarget, runMutation, withBinding]);

  const sendRequest = useCallback(async (): Promise<MutationOutcome> => {
    const targetCase = resolveCarrierTarget();
    if (!targetCase) {
      return SKIPPED_MUTATION;
    }
    return runMutation(async () => {
      await sendCarrierRequest(targetCase.id);
    });
  }, [resolveCarrierTarget, runMutation]);

  const simulateCarrierResponseAction = useCallback(async (effectiveAt: string = CARRIER_DEMO_TIMESTAMPS.simulateAt): Promise<MutationOutcome> => {
    const targetCase = resolveCarrierTarget();
    if (!targetCase) {
      return SKIPPED_MUTATION;
    }
    return runMutation(async () => {
      await simulateCarrierResponse(targetCase.id, {
        effective_at: effectiveAt,
      });
    });
  }, [resolveCarrierTarget, runMutation]);

  const approveCounterAction = useCallback(async (operatorId: string = "operator-console"): Promise<MutationOutcome> => {
    const targetCase = resolveCarrierTarget();
    if (!targetCase) {
      return SKIPPED_MUTATION;
    }
    return runMutation(async () => {
      await withBinding(
        targetCase.id,
        "COUNTER_PROPOSAL",
        async (binding) => {
          await approveCounter(targetCase.id, {
            proposal_decision_id: binding.proposal_decision_id,
            carrier_response_id: binding.carrier_response_id!,
            expected_payload_fingerprint: binding.expected_payload_fingerprint,
            operator_id: operatorId,
            status: "APPROVED",
          });
        },
      );
    });
  }, [resolveCarrierTarget, runMutation, withBinding]);

  const rejectCounterAction = useCallback(async (): Promise<MutationOutcome> => {
    const targetCase = resolveCarrierTarget();
    if (!targetCase) {
      return SKIPPED_MUTATION;
    }
    return runMutation(async () => {
      await withBinding(
        targetCase.id,
        "COUNTER_PROPOSAL",
        async (binding) => {
          await rejectCounter(targetCase.id, {
            proposal_decision_id: binding.proposal_decision_id,
            carrier_response_id: binding.carrier_response_id!,
            expected_payload_fingerprint: binding.expected_payload_fingerprint,
            operator_id: "operator-console",
          });
        },
      );
    });
  }, [resolveCarrierTarget, runMutation, withBinding]);

  const evaluateTimeoutAction = useCallback(async (): Promise<MutationOutcome> => {
    const targetCase = selectedCarrierCase;
    if (!targetCase) {
      return SKIPPED_MUTATION;
    }
    return runMutation(async () => {
      await evaluateTimeout(targetCase.id, {
        effective_at: CARRIER_DEMO_TIMESTAMPS.timeoutAt,
      });
    });
  }, [runMutation, selectedCarrierCase]);

  const bootstrapYard = useCallback(async (): Promise<MutationOutcome> => { if (latestStateRef.current.incident) return runMutation(async () => { await bootstrapDynamicYard(latestStateRef.current.incident!.id); }); return SKIPPED_MUTATION; }, [runMutation]);
  const publishActive = useCallback(async (): Promise<MutationOutcome> => { if (latestStateRef.current.incident) return runMutation(async () => { await publishDischargeActive(latestStateRef.current.incident!.id); }); return SKIPPED_MUTATION; }, [runMutation]);
  const startAgent = useCallback(async (): Promise<MutationOutcome> => { if (latestStateRef.current.incident) return runMutation(async () => { await createAgentRun(latestStateRef.current.incident!.id); }); return SKIPPED_MUTATION; }, [runMutation]);
  const startDemoAgentRun = useCallback(async (): Promise<MutationOutcome> => { if (latestStateRef.current.incident) return runMutation(async () => { await createCanonicalDemoAgentRun(latestStateRef.current.incident!.id); }); return SKIPPED_MUTATION; }, [runMutation]);
  const advanceAgent = useCallback(async (): Promise<MutationOutcome> => { const run = latestStateRef.current.agentRuns.at(-1); if (run) return runMutation(async () => { await advanceAgentRun(run.id); }); return SKIPPED_MUTATION; }, [runMutation]);
  const chooseTradeoff = useCallback(async (review: AllocationTradeoffReview, selectedOptionId: string): Promise<MutationOutcome> => { return runMutation(async () => { await selectTradeoff(review.id, { selected_option_id: selectedOptionId, expected_options_fingerprint: review.options_fingerprint, operator_id: "operator-console" }); }); }, [runMutation]);
  const createSafetyReview = useCallback(async (containerId: string): Promise<MutationOutcome> => { const currentIncident = latestStateRef.current.incident; if (currentIncident) return runMutation(async () => { await createCargoSafetyReview(currentIncident.id, containerId, "Manifest declares general cargo; free-text handling note identifies corrosive material and requires safety review.", "synthetic-canonical-cargo-note"); }); return SKIPPED_MUTATION; }, [runMutation]);
  const evaluateSafety = useCallback(async (reviewId: string): Promise<MutationOutcome> => { return runMutation(async () => { await evaluateCargoSafetyReview(reviewId); }); }, [runMutation]);

  return {
    incident,
    fixture,
    scarcityEvaluation,
    decisions,
    auditEvents,
    carrierCases,
    yardForecasts, allocationRevisions, expediteCommitments, reconsiderations, tradeoffReviews, tradeoffOptions, cargoSafetyReviews, agentRuns, selectedAgentHistory, agentWaitHistory, safetyHistories,
    canonicalStage: canonicalStage ?? initialCanonicalStageView(),
    selectedContainerId,
    selectedCarrierCaseId,
    selectedCaseHistory,
    selectedContainer,
    selectedCarrierCase,
    activeDemoRunId,
    loading,
    error,
    recoverySummary,
    containerRows,
    createCanonicalIncident,
    loadDemoRun,
    selectContainer,
    prepareCarrierRecovery,
    approveRequest: approveRequestAction,
    rejectRequest: rejectRequestAction,
    sendRequest,
    simulateCarrierResponse: simulateCarrierResponseAction,
    approveCounter: approveCounterAction,
    rejectCounter: rejectCounterAction,
    evaluateTimeout: evaluateTimeoutAction,
    bootstrapYard, publishActive, startAgent, startDemoAgentRun, advanceAgent, chooseTradeoff, createSafetyReview, evaluateSafety,
    refresh,
    readLatestState: useCallback((): { incident: Incident | null; carrierCases: CarrierRecoveryCase[]; agentRuns: AgentRun[] } => latestStateRef.current, []),
    setIncident,
    setFixture,
    setScarcityEvaluation,
    setSelectedCarrierCaseId,
  };
}
