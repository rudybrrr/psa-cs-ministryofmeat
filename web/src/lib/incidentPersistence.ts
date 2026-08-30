const STORAGE_KEY = "psa:active-incident:v1";

export function readStoredIncidentId(): string | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value && value.length > 0 ? value : null;
  } catch {
    return null;
  }
}

export function writeStoredIncidentId(incidentId: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, incidentId);
  } catch {
    // Private browsing or disabled storage — non-fatal.
  }
}

export function clearStoredIncidentId(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
