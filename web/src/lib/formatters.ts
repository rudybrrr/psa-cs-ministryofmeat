export {
  formatTimestamp,
  formatUtcClock,
  formatSgClock,
  truncateId,
} from "./format";

export function formatActionLabel(action: string): string {
  return action.replaceAll("_", " ");
}

export function formatCaseState(state: string): string {
  return state.replaceAll("_", " ").toLowerCase();
}

export function connectionShortLabel(connectionId: string): string {
  const match = connectionId.match(/SYN-CONN-(.+)$/);
  return match?.[1] ?? connectionId;
}
