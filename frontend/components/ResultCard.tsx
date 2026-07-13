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

function QuestionMark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.12" />
      <path
        d="M9.5 9.3a2.5 2.5 0 0 1 4.9.7c0 1.7-2.4 2-2.4 3.5M12 17h.01"
        stroke="currentColor"
        strokeWidth={2.1}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ResultCard({ data, onReset }: ResultCardProps) {
  const [showAll, setShowAll] = useState(false);

  // Case: even though api.ts's parseScanResponse already validates the top-
  // level shape before this component ever renders, guard here too in case
  // a future caller passes `data` in directly (e.g. from a cached/stored
  // scan) without going through that validation — `.filter()` on `undefined`
  // would otherwise crash the whole result view instead of just looking
  // a little empty.
  const allResults = Array.isArray(data.results) ? data.results : [];

  const flagged = allResults.filter((r) => r.is_flagged);
  // Only trust "verified_safe" from an actual model classification. Anything
  // else non-flagged — including verification_status === null, which means
  // the verification call didn't run or failed — falls into "uncertain".
  // We never default an unverified ingredient to "good" (see
  // services/ingredient_verify.py for why).
  const verifiedGood = allResults.filter((r) => !r.is_flagged && r.verification_status === "verified_safe");
  const uncertain = allResults.filter((r) => !r.is_flagged && r.verification_status !== "verified_safe");
  const isClean = data.flagged_count === 0;
  // Case: total_ingredients === 0 (e.g. every parsed "ingredient" somehow
  // matched nothing and got filtered out upstream) would otherwise also
  // satisfy `isClean` and show a false-positive "No harmful chemicals
  // detected" — that's a misleading safety claim when we actually found
  // nothing to check at all. Treat it as its own distinct state instead.
  const nothingToShow = data.total_ingredients === 0;

  return (
    <div className="animate-fade-in space-y-6">
      {/* Top bar: title + a clearly-visible way back to a new scan */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-ink-faint">
            Scan result · {data.total_ingredients} ingredients read
          </p>
          {/* Case: a very long product name (bad OCR read, or a legitimately
              long name) could otherwise overflow/break this header's layout
              — truncate with an ellipsis and let the full name show via the
              title tooltip on hover. */}
          <h2
            className="truncate font-display text-xl font-semibold text-ink"
            title={data.product_name || "Untitled product"}
          >
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

      {data.source_note && (
        <div className="flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs text-ink-muted">
          <svg viewBox="0 0 24 24" fill="none" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={1.5} />
            <path d="M12 8v5M12 16h.01" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" />
          </svg>
          <span>{data.source_note}</span>
        </div>
      )}

      {nothingToShow ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-caution/30 bg-caution-bg px-6 py-10 text-center">
          <QuestionMark className="h-10 w-10 text-caution" />
          <p className="font-display text-base font-semibold text-caution">
            We couldn&apos;t read any ingredients
          </p>
          <p className="max-w-sm text-sm text-ink-muted">
            Nothing usable came back from this scan — try pasting the ingredients list
            directly, or a clearer photo of the label.
          </p>
          <button
            type="button"
            onClick={onReset}
            className="mt-2 rounded-lg border border-caution/30 bg-surface px-4 py-2 text-sm font-medium text-caution hover:bg-caution-bg"
          >
            Try again
          </button>
        </div>
      ) : (
        <>
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

      {/* Verified-safe ingredients — only ones the model actually confirmed */}
      {verifiedGood.length > 0 && (
        <div className="space-y-3 rounded-xl border border-safe/30 bg-safe-bg p-4">
          <h3 className="flex items-center gap-1.5 font-display text-sm font-semibold text-safe">
            <CheckMark className="h-4 w-4" />
            Good ingredients ({verifiedGood.length})
          </h3>
          <ul className="flex flex-wrap gap-2">
            {verifiedGood.map((r, i) => (
              <li
                key={`${r.ingredient}-${i}`}
                title={r.verification_note || undefined}
                className="rounded-full border border-safe/30 bg-surface px-3 py-1 text-xs font-medium text-safe"
              >
                {r.ingredient}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Uncertain / limited-data ingredients — not flagged as harmful, but not
          confirmed safe either. Kept distinct from "Good" so a "no data"
          ingredient never reads as a positive safety claim. */}
      {uncertain.length > 0 && (
        <div className="space-y-3 rounded-xl border border-caution/30 bg-caution-bg p-4">
          <h3 className="flex items-center gap-1.5 font-display text-sm font-semibold text-caution">
            <QuestionMark className="h-4 w-4" />
            Uncertain / Limited Data ({uncertain.length})
          </h3>
          <p className="text-xs text-ink-muted">
            Not found in our flagged-chemicals database, but we couldn&apos;t confirm these as
            well-established safe either — informational only, not medical advice.
          </p>
          <ul className="flex flex-wrap gap-2">
            {uncertain.map((r, i) => (
              <li
                key={`${r.ingredient}-${i}`}
                title={r.verification_note || "No confident safety data available"}
                className="rounded-full border border-caution/30 bg-surface px-3 py-1 text-xs font-medium text-caution"
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
            {allResults.map((r, i) => (
              <li
                key={`${r.ingredient}-${i}`}
                className="flex items-center justify-between gap-3 border-b border-line/60 py-2 text-sm last:border-none"
              >
                <span className="text-ink-muted">{r.ingredient}</span>
                {r.is_flagged ? (
                  <XMark className="h-4 w-4 shrink-0 text-danger" />
                ) : r.verification_status === "verified_safe" ? (
                  <CheckMark className="h-4 w-4 shrink-0 text-safe" />
                ) : (
                  <QuestionMark className="h-4 w-4 shrink-0 text-caution" />
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
        </>
      )}

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
