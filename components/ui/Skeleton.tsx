/**
 * Placeholder blocks shown while a server component awaits its data.
 *
 * These exist because the backend is not fast: Supabase is in Singapore and a
 * cold DB-backed call measured 1.7-2.9s (see vercel.json). Without a fallback,
 * that is 1.7-2.9s of blank page with nothing to say the app is working.
 *
 * The shapes deliberately match the real content they stand in for, so the
 * layout does not jump when the data arrives. A generic spinner would be less
 * work and would tell the reader less.
 */

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-[var(--radius-sm)] bg-[var(--base-gray-200)] ${className}`}
    />
  );
}

/** One review card: square cover, then title and stat lines. */
export function ReviewCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-[var(--radius-sm)] bg-[var(--surface-card)] outline outline-1 outline-[var(--line-hairline-10)]">
      <Skeleton className="aspect-square w-full rounded-none" />
      <div className="flex flex-col gap-2 p-3">
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="mt-1 h-3 w-1/2" />
      </div>
    </div>
  );
}

/**
 * A grid of card skeletons.
 *
 * `aria-busy` with a polite live region rather than silence: a screen reader
 * user gets told the page is loading once, instead of hearing nothing and then
 * a screenful of content appearing without explanation.
 */
export function CardGridSkeleton({ count = 10 }: { count?: number }) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 md:gap-6 lg:grid-cols-5"
    >
      <span className="sr-only">Loading reviews</span>
      {Array.from({ length: count }, (_, i) => (
        <ReviewCardSkeleton key={i} />
      ))}
    </div>
  );
}

/** A stack of list rows — requests, questions. */
export function ListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div role="status" aria-busy="true" aria-live="polite" className="mt-6 flex flex-col gap-3">
      <span className="sr-only">Loading</span>
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          className="flex gap-4 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)]"
        >
          <Skeleton className="h-14 w-12 shrink-0" />
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}
