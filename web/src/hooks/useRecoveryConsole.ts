import { useCallback, useMemo, useState } from "react";

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
import type {
  AuditEvent,
  CanonicalIncidentFixture,
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
  ] = await Promise.all([
    getIncident(incidentId),
    getCanonicalFixture(),
    getScarcityEvaluation(incidentId),
    getDecisions(incidentId),
    getAuditEvents(incidentId),
    listCarrierCases(incidentId),
    listYardForecasts(incidentId), listAllocationRevisions(incidentId), listExpediteCommitments(incidentId), listReconsiderations(incidentId), listTradeoffReviews(incidentId), listTradeoffOptions(incidentId), listCargoSafetyReviews(incidentId), listAgentRuns(incidentId),
  ]);

  return {
    incident,
    fixture,
    scarcityEvaluation,
    decisions,
    auditEvents,
    carrierCases,
    yardForecasts, allocationRevisions, expediteCommitments, reconsiderations, tradeoffReviews, tradeoffOptions, cargoSafetyReviews, agentRuns,
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

  const refresh = useCallback(async () => {
    if (!incident) {
      return;
    }
    const bundle = await loadIncidentBundle(incident.id);
    setIncident(bundle.incident);
    setFixture(bundle.fixture);
    setScarcityEvaluation(bundle.scarcityEvaluation);
    setDecisions(bundle.decisions);
    setAuditEvents(bundle.auditEvents);
    setCarrierCases(bundle.carrierCases);
    setYardForecasts(bundle.yardForecasts); setAllocationRevisions(bundle.allocationRevisions); setExpediteCommitments(bundle.expediteCommitments); setReconsiderations(bundle.reconsiderations); setTradeoffReviews(bundle.tradeoffReviews); setTradeoffOptions(bundle.tradeoffOptions); setCargoSafetyReviews(bundle.cargoSafetyReviews); setAgentRuns(bundle.agentRuns);
    const currentRun = bundle.agentRuns.at(-1);
    setSelectedAgentHistory(currentRun ? await getAgentRunHistory(currentRun.id) : null);
    setAgentWaitHistory(currentRun?.wait_subject_id && ["REQUEST_APPROVAL", "COUNTER_APPROVAL", "CARRIER_RESPONSE_OR_TIMEOUT"].includes(currentRun.wait_kind ?? "") ? await getCarrierCaseHistory(currentRun.wait_subject_id) : null);
    setSafetyHistories(await Promise.all(bundle.cargoSafetyReviews.map((review) => getCargoSafetyHistory(review.id))));

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
  }, [incident, selectedCarrierCaseId, selectedContainerId]);

  const runMutation = useCallback(
    async (operation: () => Promise<void>) => {
      setLoading(true);
      setError(null);
      try {
        await operation();
        await refresh();
      } catch (mutationError) {
        if (mutationError instanceof ApiError) {
          setError(mutationError);
          if (mutationError.status === 409) {
            await refresh();
          }
        }
      } finally {
        setLoading(false);
      }
    },
    [refresh],
  );

  const createCanonicalIncident = useCallback(async () => {
    await runMutation(async () => {
      const trigger = await triggerCanonicalScarcity();
      const bundle = await loadIncidentBundle(trigger.incident_id);
      setIncident(bundle.incident);
      setFixture(bundle.fixture);
      setScarcityEvaluation(bundle.scarcityEvaluation);
      setDecisions(bundle.decisions);
      setAuditEvents(bundle.auditEvents);
      setCarrierCases(bundle.carrierCases);
      setYardForecasts(bundle.yardForecasts); setAllocationRevisions(bundle.allocationRevisions); setExpediteCommitments(bundle.expediteCommitments); setReconsiderations(bundle.reconsiderations); setTradeoffReviews(bundle.tradeoffReviews); setTradeoffOptions(bundle.tradeoffOptions); setCargoSafetyReviews(bundle.cargoSafetyReviews); setAgentRuns(bundle.agentRuns);
      setSelectedAgentHistory(null); setAgentWaitHistory(null); setSafetyHistories([]);
      setSelectedContainerId(null);
      setSelectedCarrierCaseId(null);
      setSelectedCaseHistory(null);
    });
  }, [runMutation]);

  const loadDemoRun = useCallback(
    async (runId: CanonicalDemoRunId) => {
      await runMutation(async () => {
        const run = demoRunById(runId);
        const trigger = await triggerCanonicalScarcity();
        const bundle = await loadIncidentBundle(trigger.incident_id);
        setIncident(bundle.incident);
        setFixture(bundle.fixture);
        setScarcityEvaluation(bundle.scarcityEvaluation);
        setDecisions(bundle.decisions);
        setAuditEvents(bundle.auditEvents);
        setCarrierCases(bundle.carrierCases);
        setYardForecasts(bundle.yardForecasts); setAllocationRevisions(bundle.allocationRevisions); setExpediteCommitments(bundle.expediteCommitments); setReconsiderations(bundle.reconsiderations); setTradeoffReviews(bundle.tradeoffReviews); setTradeoffOptions(bundle.tradeoffOptions); setCargoSafetyReviews(bundle.cargoSafetyReviews); setAgentRuns(bundle.agentRuns);
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
    [runMutation],
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

  const approveRequestAction = useCallback(async () => {
    if (!selectedCarrierCase) {
      return;
    }
    await runMutation(async () => {
      await withBinding(
        selectedCarrierCase.id,
        "OUTBOUND_REQUEST",
        async (binding) => {
          await approveRequest(selectedCarrierCase.id, {
            proposal_decision_id: binding.proposal_decision_id,
            request_id: binding.request_id!,
            expected_payload_fingerprint: binding.expected_payload_fingerprint,
            operator_id: "operator-console",
            status: "APPROVED",
          });
        },
      );
    });
  }, [runMutation, selectedCarrierCase, withBinding]);

  const rejectRequestAction = useCallback(async () => {
    if (!selectedCarrierCase) {
      return;
    }
    await runMutation(async () => {
      await withBinding(
        selectedCarrierCase.id,
        "OUTBOUND_REQUEST",
        async (binding) => {
          await rejectRequest(selectedCarrierCase.id, {
            proposal_decision_id: binding.proposal_decision_id,
            request_id: binding.request_id!,
            expected_payload_fingerprint: binding.expected_payload_fingerprint,
            operator_id: "operator-console",
          });
        },
      );
    });
  }, [runMutation, selectedCarrierCase, withBinding]);

  const sendRequest = useCallback(async () => {
    if (!selectedCarrierCase) {
      return;
    }
    await runMutation(async () => {
      await sendCarrierRequest(selectedCarrierCase.id);
    });
  }, [runMutation, selectedCarrierCase]);

  const simulateCarrierResponseAction = useCallback(async () => {
    if (!selectedCarrierCase) {
      return;
    }
    await runMutation(async () => {
      await simulateCarrierResponse(selectedCarrierCase.id, {
        effective_at: CARRIER_DEMO_TIMESTAMPS.simulateAt,
      });
    });
  }, [runMutation, selectedCarrierCase]);

  const approveCounterAction = useCallback(async () => {
    if (!selectedCarrierCase) {
      return;
    }
    await runMutation(async () => {
      await withBinding(
        selectedCarrierCase.id,
        "COUNTER_PROPOSAL",
        async (binding) => {
          await approveCounter(selectedCarrierCase.id, {
            proposal_decision_id: binding.proposal_decision_id,
            carrier_response_id: binding.carrier_response_id!,
            expected_payload_fingerprint: binding.expected_payload_fingerprint,
            operator_id: "operator-console",
            status: "APPROVED",
          });
        },
      );
    });
  }, [runMutation, selectedCarrierCase, withBinding]);

  const rejectCounterAction = useCallback(async () => {
    if (!selectedCarrierCase) {
      return;
    }
    await runMutation(async () => {
      await withBinding(
        selectedCarrierCase.id,
        "COUNTER_PROPOSAL",
        async (binding) => {
          await rejectCounter(selectedCarrierCase.id, {
            proposal_decision_id: binding.proposal_decision_id,
            carrier_response_id: binding.carrier_response_id!,
            expected_payload_fingerprint: binding.expected_payload_fingerprint,
            operator_id: "operator-console",
          });
        },
      );
    });
  }, [runMutation, selectedCarrierCase, withBinding]);

  const evaluateTimeoutAction = useCallback(async () => {
    if (!selectedCarrierCase) {
      return;
    }
    await runMutation(async () => {
      await evaluateTimeout(selectedCarrierCase.id, {
        effective_at: CARRIER_DEMO_TIMESTAMPS.timeoutAt,
      });
    });
  }, [runMutation, selectedCarrierCase]);

  const bootstrapYard = useCallback(async () => { if (incident) await runMutation(async () => { await bootstrapDynamicYard(incident.id); }); }, [incident, runMutation]);
  const publishActive = useCallback(async () => { if (incident) await runMutation(async () => { await publishDischargeActive(incident.id); }); }, [incident, runMutation]);
  const startAgent = useCallback(async () => { if (incident) await runMutation(async () => { await createAgentRun(incident.id); }); }, [incident, runMutation]);
  const advanceAgent = useCallback(async () => { const run = agentRuns.at(-1); if (run) await runMutation(async () => { await advanceAgentRun(run.id); }); }, [agentRuns, runMutation]);
  const chooseTradeoff = useCallback(async (review: AllocationTradeoffReview, selectedOptionId: string) => { await runMutation(async () => { await selectTradeoff(review.id, { selected_option_id: selectedOptionId, expected_options_fingerprint: review.options_fingerprint, operator_id: "operator-console" }); }); }, [runMutation]);
  const createSafetyReview = useCallback(async (containerId: string) => { if (incident) await runMutation(async () => { await createCargoSafetyReview(incident.id, containerId, "Manifest declares general cargo; free-text handling note identifies corrosive material and requires safety review.", "synthetic-canonical-cargo-note"); }); }, [incident, runMutation]);
  const evaluateSafety = useCallback(async (reviewId: string) => { await runMutation(async () => { await evaluateCargoSafetyReview(reviewId); }); }, [runMutation]);

  return {
    incident,
    fixture,
    scarcityEvaluation,
    decisions,
    auditEvents,
    carrierCases,
    yardForecasts, allocationRevisions, expediteCommitments, reconsiderations, tradeoffReviews, tradeoffOptions, cargoSafetyReviews, agentRuns, selectedAgentHistory, agentWaitHistory, safetyHistories,
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
    bootstrapYard, publishActive, startAgent, advanceAgent, chooseTradeoff, createSafetyReview, evaluateSafety,
    refresh,
    setIncident,
    setFixture,
    setScarcityEvaluation,
    setSelectedCarrierCaseId,
  };
}
