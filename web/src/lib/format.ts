export function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-SG", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "Asia/Singapore",
  }).format(date);
}

export function truncateId(value: string, visible = 8): string {
  if (value.length <= visible * 2 + 1) {
    return value;
  }

  return `${value.slice(0, visible)}…${value.slice(-visible)}`;
}
