"use client";

// Catches errors thrown in the ROOT LAYOUT itself (app/layout.tsx) — a rarer
// case than app/error.tsx (which only covers the page tree below the
// layout). Per Next.js requirements, this file must render its own
// <html>/<body> since the layout that would normally provide them is what
// crashed. Kept deliberately plain (no custom fonts/design tokens) since if
// the layout is broken, we can't assume anything above this component works.

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif" }}>
        <main
          style={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "1rem",
            background: "#FAFAF8",
          }}
        >
          <div
            style={{
              maxWidth: "24rem",
              width: "100%",
              textAlign: "center",
              border: "1px solid #E5E5E0",
              borderRadius: "1rem",
              padding: "1.75rem",
              background: "#fff",
            }}
          >
            <h1 style={{ fontSize: "1rem", fontWeight: 600, color: "#1A1A17" }}>
              ToxiScan couldn&apos;t load
            </h1>
            <p style={{ marginTop: "0.5rem", fontSize: "0.875rem", color: "#6B6B63" }}>
              Something went wrong loading the app. Please try again.
            </p>
            <button
              type="button"
              onClick={reset}
              style={{
                marginTop: "1.25rem",
                width: "100%",
                borderRadius: "0.75rem",
                background: "#1D4ED8",
                color: "#fff",
                padding: "0.6rem",
                fontSize: "0.875rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
              }}
            >
              Try again
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
