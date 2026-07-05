"use client";

// Next.js App Router error boundary: automatically wraps app/page.tsx (and
// anything it renders) in a React error boundary. This catches unexpected
// RENDER-TIME crashes (e.g. a component throwing on a malformed API
// response) — a different failure mode from the try/catch in page.tsx,
// which only handles API call rejections, not React render exceptions.
//
// Per project_rule.md ("Never expose backend errors"): deliberately does
// NOT render `error.message` or `error.stack` — those can contain internal
// details. Only a generic, friendly message is shown.

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log for developers (visible in the browser console / server logs),
    // but never rendered to the user.
    console.error("ToxiScan render error:", error);
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-4">
      <div className="w-full max-w-sm rounded-2xl border border-line bg-surface p-7 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-danger-bg">
          <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7 text-danger" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={1.5} />
            <path
              d="M12 8v5M12 16h.01"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h1 className="font-display text-base font-semibold text-ink">
          Something went wrong
        </h1>
        <p className="mt-2 text-sm text-ink-muted">
          ToxiScan hit an unexpected error. Nothing was saved — your product data
          stays private either way.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-5 w-full rounded-xl bg-primary py-2.5 text-sm font-semibold text-paper transition hover:bg-primary-hover"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
