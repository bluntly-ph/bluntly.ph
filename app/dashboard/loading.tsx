import { Skeleton } from "@/components/ui/Skeleton";

/**
 * The dashboard's shape while its summary is being fetched.
 *
 * The hero IS painted in the accent here, unlike the review page's skeleton:
 * on this screen the orange band is the design at every width, not phone-only
 * chrome, so showing it immediately holds the layout instead of flashing a
 * colour that is about to be replaced.
 */
export default function Loading() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      className="mx-auto w-full max-w-[430px] lg:max-w-[46rem]"
    >
      <span className="sr-only">Loading your earnings</span>

      <div
        className="rounded-b-[28px] pb-[96px] pt-[72px]"
        style={{
          background:
            "linear-gradient(160deg, var(--accent-primary) 0%, var(--accent-strong, #c2410c) 100%)",
        }}
      >
        <div className="flex flex-col items-center gap-2">
          <Skeleton className="h-4 w-20 bg-white/25" />
          <Skeleton className="h-10 w-48 bg-white/25" />
        </div>
      </div>

      {/* The action bar's real height, so nothing shifts when it arrives. */}
      <div className="relative z-10 -mt-[72px] px-[45px]">
        <Skeleton className="h-[72px] w-full rounded-[var(--radius-md)]" />
      </div>

      <div className="mx-4 mt-5 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-6 py-4 shadow-[var(--shadow-card)]">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-4 w-20" />
        </div>
        <div className="mt-5 flex gap-6">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="flex flex-col gap-1.5">
              <Skeleton className="h-5 w-14" />
              <Skeleton className="h-3 w-16" />
            </div>
          ))}
        </div>
        <Skeleton className="mt-6 h-[111px] w-full" />
      </div>

      <div className="mt-6 border-t border-[var(--border-subtle)] pt-4">
        <Skeleton className="mx-4 h-9 w-48 rounded-[var(--radius-pill)]" />
        {Array.from({ length: 3 }, (_, i) => (
          <div
            key={i}
            className="flex items-center gap-3 border-b border-[var(--border-subtle)] px-4 py-5 last:border-0"
          >
            <Skeleton className="h-20 w-20 shrink-0" />
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <Skeleton className="h-3.5 w-4/5" />
              <Skeleton className="h-3 w-3/5" />
              <Skeleton className="h-4 w-16" />
            </div>
            <Skeleton className="h-[70px] w-[100px] shrink-0" />
          </div>
        ))}
      </div>
    </div>
  );
}
