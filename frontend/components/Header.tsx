export default function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-paper/90 backdrop-blur">
      <div className="mx-auto flex max-w-xl items-center gap-2 px-4 py-4">
        <svg viewBox="0 0 32 32" className="h-7 w-7 shrink-0" aria-hidden="true">
          <path
            d="M16 3 27 7.5v8C27 22.5 22.3 27.6 16 29 9.7 27.6 5 22.5 5 15.5v-8L16 3Z"
            fill="#1D4ED8"
          />
          <path
            d="m11.5 16 3 3 6-6.5"
            stroke="#FAFAF8"
            strokeWidth={2.2}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
        <span className="font-display text-lg font-bold tracking-tight text-ink">
          ToxiScan
        </span>
      </div>
    </header>
  );
}
