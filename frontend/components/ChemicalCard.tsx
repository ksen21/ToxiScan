import { IngredientResult } from "@/lib/types";
import { toneForSeverity } from "@/lib/tone";

interface ChemicalCardProps {
  result: IngredientResult;
}

export default function ChemicalCard({ result }: ChemicalCardProps) {
  const tone = toneForSeverity(result.severity);

  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-1.5">
          <svg viewBox="0 0 24 24" fill="none" className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true">
            <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.12" />
            <path d="m8.5 8.5 7 7m0-7-7 7" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" />
          </svg>
          <div>
            <p className="font-mono text-sm font-semibold text-ink">
              {result.matched_chemical ?? result.ingredient}
            </p>
            {result.matched_chemical && result.matched_chemical !== result.ingredient && (
              <p className="text-xs text-ink-faint">as listed: “{result.ingredient}”</p>
            )}
          </div>
        </div>
        {result.severity && (
          <span
            className={`shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide ${tone.text} ${tone.bg} ${tone.border}`}
          >
            {result.severity}
          </span>
        )}
      </div>

      {result.concerns.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {result.concerns.map((concern) => (
            <li
              key={concern}
              className="rounded border border-line bg-ink/[0.03] px-2 py-0.5 text-xs text-ink-muted"
            >
              {concern}
            </li>
          ))}
        </ul>
      )}

      {result.research_url && (
        <a
          href={result.research_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary-hover hover:underline"
        >
          Read the research
          <svg viewBox="0 0 24 24" fill="none" className="h-3 w-3" aria-hidden="true">
            <path
              d="M7 17 17 7M9 7h8v8"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </a>
      )}
    </div>
  );
}
