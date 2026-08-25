import { Skeleton } from "@/components/ui/Skeleton";

/**
 * The admin console's shape while its data is being fetched.
 *
 * `/moderate` makes three backend calls before it can render — the queue, the
 * reports, and the overview — and had no loading state at all, so a moderator
 * got a blank screen for as long as the slowest of them took.
 *
 * Deliberately neutral. The console is a white sidebar beside a light working
 * area at every width, so there is no accent to hold: the only loading state in
 * the app that paints the brand colour is the dashboard, whose hero is orange
 * in its own frame.
 */
export default function Loading() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      className="flex min-h-dvh bg-[var(--surface-app)]"
    >
      <span className="sr-only">Loading the moderation console</span>

      {/* The real 220px rail, so the working area does not start wide and
          then snap narrower when the sidebar arrives. */}
      <aside className="hidden w-[220px] shrink-0 flex-col gap-6 border-r border-[var(--border-subtle)] bg-[var(--surface-card)] px-3 py-5 lg:flex">
        <Skeleton className="mx-3 h-8 w-24" />
        {Array.from({ length: 4 }, (_, group) => (
          <div key={group} className="flex flex-col gap-2">
            <Skeleton className="mx-3 h-2.5 w-16" />
            {Array.from({ length: group === 0 ? 3 : 2 }, (_, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ))}
        <Skeleton className="mt-auto h-14 w-full" />
      </aside>

      <div className="min-w-0 flex-1 px-4 py-5 sm:px-8">
        <Skeleton className="h-11 w-40 rounded-[var(--radius-md)]" />

        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div
              key={i}
              className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
            >
              <Skeleton className="h-3.5 w-24" />
              <Skeleton className="mt-2 h-9 w-16" />
              <Skeleton className="mt-3 h-3 w-28" />
            </div>
          ))}
        </div>

        <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_26rem]">
          <div className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
            <Skeleton className="h-3 w-32" />
            <div className="mt-4 flex flex-col gap-2.5">
              {Array.from({ length: 5 }, (_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          </div>

          <div className="rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
            <Skeleton className="h-3 w-32" />
            <div className="mt-4 flex flex-col gap-4">
              {Array.from({ length: 4 }, (_, i) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <Skeleton className="h-3.5 w-full" />
                  <Skeleton className="h-2 w-full" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
