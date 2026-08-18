import { CardGridSkeleton, Skeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="mx-auto w-full max-w-[72rem] px-6 py-8 lg:px-10 lg:py-10">
      <Skeleton className="h-7 w-56" />
      <Skeleton className="mt-2 h-4 w-40" />
      <CardGridSkeleton count={10} />
    </div>
  );
}
