import { request } from "./client";
import type { CargoSafetyEvaluationResult, CargoSafetyHistory, CargoSafetyReview } from "./types";
export const createCargoSafetyReview = (id: string, container_id: string, text: string, source = "operator-console") => request<CargoSafetyReview>(`/incidents/${id}/cargo-safety-reviews`, { method: "POST", body: JSON.stringify({ container_id, note: { text, source } }) });
export const evaluateCargoSafetyReview = (id: string) => request<CargoSafetyEvaluationResult>(`/cargo-safety-reviews/${id}/evaluate`, { method: "POST" });
export const listCargoSafetyReviews = (id: string) => request<CargoSafetyReview[]>(`/incidents/${id}/cargo-safety-reviews`);
export const getCargoSafetyHistory = (id: string) => request<CargoSafetyHistory>(`/cargo-safety-reviews/${id}/history`);
