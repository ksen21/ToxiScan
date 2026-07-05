import { toneForLabel } from "@/lib/tone";

interface VerdictProps {
  label: string;
  flaggedCount: number;
  totalIngredients: number;
}

const COPY: Record<string, string> = {
  Safe: "No significant concerns found in this ingredient list.",
  Moderate: "A few ingredients are worth a second look, but nothing severe.",
  Risky: "Several flagged ingredients — check the details below before using.",
  Dangerous: "Multiple high-concern ingredients detected. Review carefully.",
};

function Icon({ label, className }: { label: string; className?: string }) {
  if (label === "Safe") {
    return (
      <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
        <path
          d="M20 6 9 17l-5-5"
          stroke="currentColor"
          strokeWidth={2.4}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (label === "Dangerous") {
    return (
      <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
        <path
          d="M12 9v4m0 4h.01M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L14.7 3.86a2 2 0 0 0-3.4 0Z"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth={2} />
      <path d="M12 8v5" stroke="currentColor" strokeWidth={2} strokeLinecap="round" />
      <circle cx="12" cy="16" r="1" fill="currentColor" />
    </svg>
  );
}

export default function Verdict({ label, flaggedCount, totalIngredients }: VerdictProps) {
  const tone = toneForLabel(label);
  const copy = COPY[label] ?? COPY.Moderate;

  return (
    <div className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${tone.bg} ${tone.border}`}>
      <Icon label={label} className={`mt-0.5 h-5 w-5 shrink-0 ${tone.text}`} />
      <div>
        <p className={`font-display text-sm font-semibold ${tone.text}`}>{copy}</p>
        <p className="mt-0.5 text-xs text-ink-muted">
          {flaggedCount} of {totalIngredients} ingredients flagged
        </p>
      </div>
    </div>
  );
}
