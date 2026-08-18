"use client";

import { RouteError } from "@/components/site/RouteError";

export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return <RouteError error={error} retry={unstable_retry} what="this review" />;
}
