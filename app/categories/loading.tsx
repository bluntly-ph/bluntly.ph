import { Skeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="mx-auto w-full max-w-[72rem] px-6 py-8 lg:px-10 lg:py-10">
      <Skeleton className="h-7 w-44" />
      <div
        role="status"
        aria-busy="true"
        aria-live="polite"
        className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
      >
        <span className="sr-only">Loading categories</span>
        {Array.from({ length: 14 }, (_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    </div>
  );
}
