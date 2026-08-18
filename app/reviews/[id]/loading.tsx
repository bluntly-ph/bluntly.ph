import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Mirrors the review's own layout: the orange nav bar is painted for real
 * rather than skeletonised, because it is static chrome that needs no data.
 * Showing it immediately means the way back is available while the review is
 * still loading.
 */
export default function Loading() {
  return (
    <>
      <div className="h-[72px] w-full bg-[var(--accent-primary)]" />
      <div
        role="status"
        aria-busy="true"
        aria-live="polite"
        className="mx-auto w-full max-w-[44rem] px-4 py-6 lg:px-6 lg:py-10"
      >
        <span className="sr-only">Loading review</span>
        <div className="flex items-center gap-2">
          <Skeleton className="h-9 w-9 rounded-full" />
          <Skeleton className="h-4 w-40" />
        </div>
        <Skeleton className="mt-4 h-6 w-5/6" />
        <Skeleton className="mt-2 h-6 w-2/3" />
        <Skeleton className="mt-5 aspect-square w-full rounded-[16px]" />
        <Skeleton className="mt-6 h-4 w-32" />
        <div className="mt-3 flex flex-col gap-2">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
        </div>
      </div>
    </>
  );
}
