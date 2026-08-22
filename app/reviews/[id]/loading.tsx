import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Mirrors the review's own layout at every width.
 *
 * The orange bar is the review's **phone** chrome. It used to be painted here
 * at all widths, which was right when the page carried it at all widths — but
 * the desktop redesign hides it from `md` and renders `SiteHeader` instead, so
 * this was slabbing 72px of brand orange across a 1440px screen a moment before
 * a white header replaced it. That flash is the orange the owner saw.
 *
 * A loading state's job is to hold the shape of the thing arriving. Painting
 * the wrong chrome is worse than painting none, because the layout visibly
 * jumps when the real page lands.
 *
 * The bar is still painted for real below `md` rather than skeletonised: it is
 * static chrome that needs no data, and showing it immediately means the way
 * back exists while the review is still loading.
 */
export default function Loading() {
  return (
    <>
      {/* Phone: the real orange nav. Tablet and up: the height SiteHeader
          occupies, in the page's own surface colour rather than the accent. */}
      <div className="h-[72px] w-full bg-[var(--accent-primary)] md:hidden" />
      <div className="hidden h-16 w-full border-b border-[var(--border-subtle)] bg-[var(--surface-app)] md:block md:h-[72px]" />

      <div
        role="status"
        aria-busy="true"
        aria-live="polite"
        className="mx-auto w-full lg:max-w-[76rem] lg:px-10 lg:py-10"
      >
        <span className="sr-only">Loading review</span>

        <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start lg:gap-12">
          {/* Reading column — the same 44rem/42rem it resolves to. */}
          <div className="mx-auto w-full max-w-[44rem] px-4 py-6 lg:mx-0 lg:max-w-[42rem] lg:px-0 lg:py-0">
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-9 rounded-full" />
              <Skeleton className="h-4 w-40" />
            </div>
            <Skeleton className="mt-4 h-6 w-5/6" />
            <Skeleton className="mt-2 h-6 w-2/3" />
            {/* Matches the hero's real ratio, including the shorter desktop
                crop — an aspect-square placeholder reserved a third more height
                than the image that replaced it. */}
            <Skeleton className="mt-6 aspect-[16/10] w-full lg:aspect-[16/7]" />
            <Skeleton className="mt-6 h-4 w-32" />
            <div className="mt-3 flex flex-col gap-2">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
            </div>
          </div>

          {/* Desktop context column, so the grid does not collapse and then
              re-expand when the sidebar arrives. */}
          <div className="hidden lg:flex lg:flex-col lg:gap-8">
            <div className="flex flex-col gap-3">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="aspect-[4/3] w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-9 w-full rounded-[var(--radius-pill)]" />
            </div>
            <div className="flex flex-col gap-2">
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-20 w-full" />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
