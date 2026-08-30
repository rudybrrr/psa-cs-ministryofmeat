export interface ConsoleErrorPresentation {
  title: string;
  detail: string;
}

export function describeConsoleError(error: {
  status: number;
  detail: string;
}): ConsoleErrorPresentation {
  const trimmed = error.detail.trim();

  if (error.status === 0) {
    return {
      title: "Couldn't reach the server",
      detail:
        "Check that the backend is running and reachable, then try again.",
    };
  }

  if (error.status >= 500) {
    return {
      title: "Server error",
      detail: trimmed || "The backend returned an unexpected error. Try again in a moment.",
    };
  }

  if (error.status === 404) {
    return {
      title: "Recovery session not found",
      detail: trimmed || "The requested incident or resource no longer exists.",
    };
  }

  if (error.status === 409) {
    return {
      title: "Action blocked",
      detail: trimmed || "Complete the required step before advancing again.",
    };
  }

  if (error.status === 403) {
    return {
      title: "Not permitted",
      detail: trimmed || "This action is not allowed in the current recovery state.",
    };
  }

  return {
    title: "Something went wrong",
    detail: trimmed || "An unexpected error occurred while loading recovery data.",
  };
}
