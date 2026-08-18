import { CardGridSkeleton, Skeleton } from "@/components/ui/Skeleton";

/**
 * The landing page. The hero's copy is static, but it renders inside the same
 * server component as the feed, so the whole route suspends together — the
 * skeleton stands in for both.
 */
export default function Loading() {
  return (
    <div className="mx-auto w-full max-w-[72rem] px-6 py-14 lg:px-10 lg:py-20">
      <div className="grid gap-12 md:grid-cols-2 md:items-center">
        <div>
          <Skeleton className="h-10 w-3/4" />
          <Skeleton className="mt-3 h-10 w-5/6" />
          <Skeleton className="mt-4 h-4 w-56" />
          <Skeleton className="mt-8 h-12 w-full max-w-[34rem] rounded-[32px]" />
        </div>
        <Skeleton className="mx-auto h-[200px] w-full max-w-[26rem] rounded-[12px]" />
      </div>
      <CardGridSkeleton count={5} />
    </div>
  );
}
