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
import type {
  AuditEvent,
  CanonicalIncidentFixture,
  CarrierRecoveryCase,
  CarrierRecoveryHistory,
  Decision,
  Incident,
  ScarcityEvaluationReport,
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
  ] = await Promise.all([
    getIncident(incidentId),
    getCanonicalFixture(),
    getScarcityEvaluation(incidentId),
    getDecisions(incidentId),
    getAuditEvents(incidentId),
    listCarrierCases(incidentId),
  ]);

  return {
    incident,
    fixture,
    scarcityEvaluation,
    decisions,
    auditEvents,
    carrierCases,
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
    );
  }, [fixture, scarcityEvaluation, decisions, carrierCases]);

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

  return {
    incident,
    fixture,
    scarcityEvaluation,
    decisions,
    auditEvents,
    carrierCases,
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
    refresh,
    setIncident,
    setFixture,
    setScarcityEvaluation,
    setSelectedCarrierCaseId,
  };
}
