function Block({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-md ${className}`} />;
}

export function ResultSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Analyzing ingredients">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <Block className="h-3 w-20" />
          <Block className="h-6 w-40" />
        </div>
        <Block className="h-3 w-24" />
      </div>

      <div className="flex flex-col items-center gap-4 rounded-xl border border-line bg-surface p-6">
        <div className="skeleton h-[130px] w-[220px] rounded-full [clip-path:polygon(0_0,100%_0,100%_50%,0_50%)]" />
        <Block className="h-9 w-24" />
        <Block className="h-5 w-20 rounded-full" />
      </div>

      <Block className="h-14 w-full rounded-lg" />

      <div className="space-y-3">
        <Block className="h-4 w-40" />
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="space-y-3 rounded-lg border border-line bg-surface p-4">
              <div className="flex items-start justify-between gap-2">
                <Block className="h-4 w-28" />
                <Block className="h-5 w-16 rounded-full" />
              </div>
              <div className="flex gap-1.5">
                <Block className="h-5 w-16 rounded" />
                <Block className="h-5 w-20 rounded" />
              </div>
              <Block className="h-3 w-24" />
            </div>
          ))}
        </div>
      </div>

      <Block className="h-12 w-full rounded-xl" />
      <Block className="h-12 w-full rounded-lg" />
    </div>
  );
}

export function CenteredLoader({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-primary" />
      <p className="text-sm text-ink-muted">{label}</p>
    </div>
  );
}
