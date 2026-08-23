import { request } from "./client";
import type {
  CanonicalIncidentFixture,
  ScarcityEvaluationReport,
  ScarcityTriggerResponse,
} from "./types";

export async function triggerCanonicalScarcity(): Promise<ScarcityTriggerResponse> {
  return request<ScarcityTriggerResponse>("/synthetic/scenarios/canonical-scarcity", {
    method: "POST",
  });
}

export async function getCanonicalFixture(): Promise<CanonicalIncidentFixture> {
  return request<CanonicalIncidentFixture>(
    "/synthetic/scenarios/canonical-scarcity/fixture",
  );
}

export async function getScarcityEvaluation(
  incidentId: string,
): Promise<ScarcityEvaluationReport> {
  return request<ScarcityEvaluationReport>(
    `/incidents/${incidentId}/scarcity-evaluation`,
  );
}
