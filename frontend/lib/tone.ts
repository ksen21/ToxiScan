import { SeverityLevel } from "./types";

export type LabelTone = {
  text: string;
  bg: string;
  border: string;
  hex: string;
};

const LABEL_TONES: Record<string, LabelTone> = {
  Safe: { text: "text-safe", bg: "bg-safe-bg", border: "border-safe/30", hex: "#16794F" },
  Moderate: { text: "text-caution", bg: "bg-caution-bg", border: "border-caution/30", hex: "#B45309" },
  Risky: { text: "text-risky", bg: "bg-risky-bg", border: "border-risky/30", hex: "#C2410C" },
  Dangerous: { text: "text-danger", bg: "bg-danger-bg", border: "border-danger/30", hex: "#B91C1C" },
};

export function toneForLabel(label: string): LabelTone {
  return LABEL_TONES[label] ?? LABEL_TONES.Moderate;
}

const SEVERITY_TONES: Record<SeverityLevel, LabelTone> = {
  low: { text: "text-safe", bg: "bg-safe-bg", border: "border-safe/30", hex: "#16794F" },
  moderate: { text: "text-caution", bg: "bg-caution-bg", border: "border-caution/30", hex: "#B45309" },
  high: { text: "text-risky", bg: "bg-risky-bg", border: "border-risky/30", hex: "#C2410C" },
  critical: { text: "text-danger", bg: "bg-danger-bg", border: "border-danger/30", hex: "#B91C1C" },
};

export function toneForSeverity(severity: SeverityLevel | null): LabelTone {
  if (!severity) return { text: "text-ink-muted", bg: "bg-ink/5", border: "border-line", hex: "#5B5F66" };
  return SEVERITY_TONES[severity];
}
