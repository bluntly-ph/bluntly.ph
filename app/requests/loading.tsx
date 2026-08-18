import { ListSkeleton, Skeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="mx-auto w-full max-w-[52rem] px-6 py-8 lg:py-10">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="mt-2 h-4 w-72" />
      <ListSkeleton count={4} />
    </div>
  );
}
