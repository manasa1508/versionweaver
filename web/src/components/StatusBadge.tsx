import { Circle } from "lucide-react";
import { titleCase } from "../lib/format";

const positive = new Set(["ok", "succeeded", "published"]);
const warning = new Set(["planned", "queued", "leased", "running", "verifying", "approved"]);
const negative = new Set(["failed", "blocked", "dead_letter", "degraded"]);

export function StatusBadge({ value }: { value: string }) {
  const tone = positive.has(value)
    ? "positive"
    : warning.has(value)
      ? "warning"
      : negative.has(value)
        ? "negative"
        : "neutral";
  return (
    <span className={`status-badge status-${tone}`}>
      <Circle size={7} fill="currentColor" aria-hidden="true" />
      {titleCase(value)}
    </span>
  );
}
