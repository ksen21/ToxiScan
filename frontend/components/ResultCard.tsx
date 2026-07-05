"use client";

import { useState } from "react";
import { ScanResponse } from "@/lib/types";
import ScoreGauge from "./ScoreGauge";
import Verdict from "./Verdict";
import ChemicalCard from "./ChemicalCard";

interface ResultCardProps {
  data: ScanResponse;
  onReset: () => void;
}

function XMark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.12" />
      <path d="m8.5 8.5 7 7m0-7-7 7" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" />
    </svg>
  );
}

function CheckMark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.12" />
      <path d="m7.5 12.5 3 3 6-6.5" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function ResultCard({ data, onReset }: ResultCardProps) {
  const [showAll, setShowAll] = useState(false);
  const flagged = data.results.filter((r) => r.is_flagged);
  const good = data.results.filter((r) => !r.is_flagged);
  const isClean = data.flagged_count === 0;

  return (
    <div className="animate-fade-in space-y-6">
      {/* Top bar: title + a clearly-visible way back to a new scan */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-faint">
            Scan result · {data.total_ingredients} ingredients read
          </p>
          <h2 className="font-display text-xl font-semibold text-ink">
            {data.product_name || "Untitled product"}
          </h2>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-line bg-surface px-3 py-2 text-xs font-medium text-ink transition-colors hover:bg-ink/[0.04]"
        >
          <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
            <path
              d="M4 4v6h6M20 20v-6h-6M4.5 15a8 8 0 0 0 14.5 3.5M19.5 9A8 8 0 0 0 5 5.5"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          New scan
        </button>
      </div>

      <div className="rounded-xl border border-line bg-surface p-6">
        <ScoreGauge scoreOutOf10={data.score_out_of_10} label={data.safety_label} />
      </div>

      <Verdict
        label={data.safety_label}
        flaggedCount={data.flagged_count}
        totalIngredients={data.total_ingredients}
      />

      {isClean ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-safe/30 bg-safe-bg px-6 py-10 text-center">
          <CheckMark className="h-10 w-10 text-safe" />
          <p className="font-display text-base font-semibold text-safe">
            No harmful chemicals detected
          </p>
          <p className="max-w-sm text-sm text-ink-muted">
            Every ingredient we could match came back clear against our database.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <h3 className="flex items-center gap-1.5 font-display text-sm font-semibold text-danger">
            <XMark className="h-4 w-4" />
            Flagged ingredients ({flagged.length})
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {flagged.map((result, i) => (
              <ChemicalCard key={`${result.ingredient}-${i}`} result={result} />
            ))}
          </div>
        </div>
      )}

      {/* Good ingredients — separate, positively-colored list */}
      {good.length > 0 && (
        <div className="space-y-3 rounded-xl border border-safe/30 bg-safe-bg p-4">
          <h3 className="flex items-center gap-1.5 font-display text-sm font-semibold text-safe">
            <CheckMark className="h-4 w-4" />
            Good ingredients ({good.length})
          </h3>
          <ul className="flex flex-wrap gap-2">
            {good.map((r, i) => (
              <li
                key={`${r.ingredient}-${i}`}
                className="rounded-full border border-safe/30 bg-surface px-3 py-1 text-xs font-medium text-safe"
              >
                {r.ingredient}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="rounded-xl border border-line bg-surface">
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-ink"
          aria-expanded={showAll}
        >
          All ingredients ({data.total_ingredients})
          <svg
            viewBox="0 0 24 24"
            fill="none"
            className={`h-4 w-4 text-ink-faint transition-transform ${showAll ? "rotate-180" : ""}`}
            aria-hidden="true"
          >
            <path d="m6 9 6 6 6-6" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        {showAll && (
          <ul className="border-t border-line px-4 py-3">
            {data.results.map((r, i) => (
              <li
                key={`${r.ingredient}-${i}`}
                className="flex items-center justify-between gap-3 border-b border-line/60 py-2 text-sm last:border-none"
              >
                <span className="text-ink-muted">{r.ingredient}</span>
                {r.is_flagged ? (
                  <XMark className="h-4 w-4 shrink-0 text-danger" />
                ) : (
                  <CheckMark className="h-4 w-4 shrink-0 text-safe" />
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <button
        type="button"
        onClick={onReset}
        className="w-full rounded-lg border border-line bg-surface py-3 text-sm font-medium text-ink transition-colors hover:bg-ink/[0.03]"
      >
        Check another product
      </button>
    </div>
  );
}
