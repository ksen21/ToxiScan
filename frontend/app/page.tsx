"use client";

import { useRef, useState } from "react";
import UploadForm from "@/components/UploadForm";
import ResultCard from "@/components/ResultCard";
import Header from "@/components/Header";
import { ResultSkeleton } from "@/components/Skeletons";
import { scanText, scanImage, scanByProductName } from "@/lib/api";
import { ScanResponse } from "@/lib/types";

type Status = "idle" | "loading" | "success" | "error";

const COLD_START_DELAY_MS = 5000;

export default function Home() {
  const [status, setStatus] = useState<Status>("idle");
  const [data, setData] = useState<ScanResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Case: user resets and fires a second scan before the first one's promise
  // has settled (e.g. "New scan" -> immediately submit again while an old
  // request is still in flight, or a network retry lands late). Without
  // this, a slow first request that resolves AFTER a newer one could
  // overwrite the newer result with stale data. Each request captures the
  // generation it was started at; only the still-current generation is
  // allowed to update state when it resolves.
  const requestGeneration = useRef(0);

  function beginRequest(): number {
    const generation = ++requestGeneration.current;
    setStatus("loading");
    setSlow(false);
    setErrorMsg(null);
    slowTimer.current = setTimeout(() => {
      if (requestGeneration.current === generation) setSlow(true);
    }, COLD_START_DELAY_MS);
    return generation;
  }

  function endRequest() {
    if (slowTimer.current) clearTimeout(slowTimer.current);
  }

  function applyResult(generation: number, result: ScanResponse) {
    if (requestGeneration.current !== generation) return; // stale — a newer request has since started
    setData(result);
    setStatus("success");
  }

  function applyError(generation: number, err: unknown) {
    if (requestGeneration.current !== generation) return; // stale — a newer request has since started
    setErrorMsg(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    setStatus("error");
  }

  async function handleSubmitText(ingredientsText: string, productName: string) {
    const generation = beginRequest();
    try {
      const result = await scanText(ingredientsText, productName);
      applyResult(generation, result);
    } catch (err) {
      applyError(generation, err);
    } finally {
      endRequest();
    }
  }

  async function handleSubmitImage(file: File, productName: string) {
    const generation = beginRequest();
    try {
      const result = await scanImage(file, productName);
      applyResult(generation, result);
    } catch (err) {
      applyError(generation, err);
    } finally {
      endRequest();
    }
  }

  async function handleSubmitProductName(productName: string) {
    const generation = beginRequest();
    try {
      const result = await scanByProductName(productName);
      applyResult(generation, result);
    } catch (err) {
      applyError(generation, err);
    } finally {
      endRequest();
    }
  }

  function reset() {
    requestGeneration.current++; // invalidates any still-in-flight request
    endRequest();
    setStatus("idle");
    setData(null);
    setErrorMsg(null);
  }

  return (
    <main className="min-h-screen bg-paper">
      <Header />
      <div className="mx-auto max-w-xl px-4 pb-16 pt-8 sm:pt-12">
        <header className="mb-8 text-center">
          <h1 className="font-display text-3xl font-semibold leading-tight text-ink sm:text-4xl">
            Know what&apos;s really in it.
          </h1>
          <p className="mx-auto mt-3 max-w-sm text-sm text-ink-muted">
            Paste an ingredients list or photograph a label. We check it against a
            database of flagged cosmetic chemicals and give you a plain-language reading.
          </p>
        </header>

        <div className="rounded-2xl border border-line bg-surface p-5 shadow-sm sm:p-7">
          {status === "idle" && (
            <UploadForm
              onSubmitText={handleSubmitText}
              onSubmitImage={handleSubmitImage}
              onSubmitProductName={handleSubmitProductName}
            />
          )}

          {status === "loading" && (
            <>
              {slow && (
                <div className="mb-5 flex items-center gap-2 rounded-lg border border-caution/30 bg-caution-bg px-3 py-2 text-xs text-caution">
                  <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-caution" />
                  Waking up the server — first request can take up to a minute.
                </div>
              )}
              <ResultSkeleton />
            </>
          )}

          {status === "success" && data && <ResultCard data={data} onReset={reset} />}

          {status === "error" && (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <svg viewBox="0 0 24 24" fill="none" className="h-9 w-9 text-danger" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={1.5} />
                <path d="M15 9l-6 6M9 9l6 6" stroke="currentColor" strokeWidth={2} strokeLinecap="round" />
              </svg>
              <p className="font-display text-sm font-semibold text-ink">Couldn&apos;t complete the scan</p>
              <p className="max-w-xs text-sm text-ink-muted">{errorMsg}</p>
              <button
                type="button"
                onClick={reset}
                className="mt-1 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-ink/[0.03]"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
