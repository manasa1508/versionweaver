const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

function parseApiDate(value: string): Date {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(parseApiDate(value));
}

export function timeAgo(value: string): string {
  const deltaSeconds = (parseApiDate(value).getTime() - Date.now()) / 1000;
  const ranges: Array<[number, Intl.RelativeTimeFormatUnit]> = [
    [60, "second"],
    [60, "minute"],
    [24, "hour"],
    [7, "day"],
    [4.345, "week"],
    [12, "month"],
    [Number.POSITIVE_INFINITY, "year"]
  ];
  let valueInUnit = deltaSeconds;
  for (const [divisor, unit] of ranges) {
    if (Math.abs(valueInUnit) < divisor) return relative.format(Math.round(valueInUnit), unit);
    valueInUnit /= divisor;
  }
  return "recently";
}

export function shortId(value: string): string {
  return value.slice(0, 8);
}

export function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function riskLabel(score: number): "low" | "medium" | "high" {
  if (score >= 70) return "high";
  if (score >= 35) return "medium";
  return "low";
}
