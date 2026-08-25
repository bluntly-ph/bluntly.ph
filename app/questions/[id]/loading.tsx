import { Skeleton } from "@/components/ui/Skeleton";

/**
 * A neutral, layout-faithful placeholder for a server-fetched page.
 *
 * This route rendered nothing at all while it awaited the backend, which on a
 * cold Supabase call is over a second of blank screen. The shapes match the
 * real content's proportions so the layout does not jump when it arrives, and
 * carry no accent colour — the brand orange belongs to surfaces whose own
 * design is orange, not to waiting.
 */
export default function Loading() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      className="mx-auto w-full max-w-[64rem] flex-1 px-6 py-8 lg:py-10"
    >
      <span className="sr-only">Loading</span>

      <div className="flex items-center gap-4">
        <Skeleton className="h-16 w-16 shrink-0 rounded-full" />
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-3.5 w-64" />
        </div>
      </div>

      <div className="mt-8 flex flex-col gap-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div
            key={i}
            className="flex gap-4 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)]"
          >
            <Skeleton className="h-16 w-16 shrink-0" />
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
