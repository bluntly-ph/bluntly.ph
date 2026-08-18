import { ListSkeleton, Skeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="mx-auto w-full max-w-[52rem] px-6 py-8 lg:py-10">
      <Skeleton className="h-7 w-40" />
      <Skeleton className="mt-2 h-4 w-64" />
      <ListSkeleton count={5} />
    </div>
  );
}
