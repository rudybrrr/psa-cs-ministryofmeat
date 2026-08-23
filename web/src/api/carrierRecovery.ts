import { request } from "./client";
import type {
  Approval,
  CarrierRecoveryCase,
  CarrierRecoveryHistory,
  CarrierSimulationResult,
  CounterApprovalBody,
  EffectiveAtBody,
  PrepareCarrierRecoveryBody,
  RequestApprovalBody,
  RTARequestContext,
} from "./types";

export async function prepareCarrierRecovery(
  incidentId: string,
  body: PrepareCarrierRecoveryBody,
): Promise<CarrierRecoveryCase> {
  return request<CarrierRecoveryCase>(
    `/incidents/${incidentId}/carrier-recovery-cases`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function listCarrierCases(
  incidentId: string,
): Promise<CarrierRecoveryCase[]> {
  return request<CarrierRecoveryCase[]>(
    `/incidents/${incidentId}/carrier-recovery-cases`,
  );
}

export async function getCarrierCase(caseId: string): Promise<CarrierRecoveryCase> {
  return request<CarrierRecoveryCase>(`/carrier-recovery-cases/${caseId}`);
}

export async function getCarrierCaseHistory(
  caseId: string,
): Promise<CarrierRecoveryHistory> {
  return request<CarrierRecoveryHistory>(
    `/carrier-recovery-cases/${caseId}/history`,
  );
}

export async function approveRequest(
  caseId: string,
  body: RequestApprovalBody,
): Promise<Approval> {
  return request<Approval>(
    `/carrier-recovery-cases/${caseId}/request-approval`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function rejectRequest(
  caseId: string,
  body: Omit<RequestApprovalBody, "status">,
): Promise<Approval> {
  return approveRequest(caseId, { ...body, status: "REJECTED" });
}

export async function sendCarrierRequest(
  caseId: string,
): Promise<RTARequestContext> {
  return request<RTARequestContext>(`/carrier-recovery-cases/${caseId}/send`, {
    method: "POST",
  });
}

export async function simulateCarrierResponse(
  caseId: string,
  body: EffectiveAtBody,
): Promise<CarrierSimulationResult> {
  return request<CarrierSimulationResult>(
    `/carrier-recovery-cases/${caseId}/simulate-carrier-response`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function approveCounter(
  caseId: string,
  body: CounterApprovalBody,
): Promise<Approval> {
  return request<Approval>(
    `/carrier-recovery-cases/${caseId}/counter-approval`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function rejectCounter(
  caseId: string,
  body: Omit<CounterApprovalBody, "status">,
): Promise<Approval> {
  return approveCounter(caseId, { ...body, status: "REJECTED" });
}

export async function evaluateTimeout(
  caseId: string,
  body: EffectiveAtBody,
): Promise<CarrierRecoveryCase> {
  return request<CarrierRecoveryCase>(
    `/carrier-recovery-cases/${caseId}/evaluate-timeout`,
    { method: "POST", body: JSON.stringify(body) },
  );
}
