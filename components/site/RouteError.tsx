"use client";

import { useEffect } from "react";
import { ArrowClockwise, WarningCircle } from "@phosphor-icons/react";

import { Button } from "@/components/ui/Button";

/**
 * Shared body for every route's error.tsx.
 *
 * Note the prop is `unstable_retry`, not `reset` — this Next renamed it, and a
 * handler wired to `reset` is simply undefined at runtime, so the button
 * renders and does nothing. See
 * node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/error.md
 *
 * The message deliberately does not show `error.message`: these are server
 * errors and the text can carry internals. The digest is shown instead, which
 * is the handle support needs to find it in the logs and means nothing to an
 * attacker.
 */
export function RouteError({
  error,
  retry,
  what,
}: {
  error: Error & { digest?: string };
  retry: () => void;
  /** What failed to load, in the reader's terms — "reviews", "this review". */
  what: string;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex w-full max-w-[32rem] flex-col items-center px-6 py-16 text-center">
      <WarningCircle size={40} className="text-[var(--accent-danger)]" />
      <h1 className="mt-4 text-[20px] font-semibold text-[var(--text-primary)]">
        Couldn&rsquo;t load {what}
      </h1>
      <p className="mt-2 text-[14px] text-[var(--text-secondary)]">
        Something went wrong on our side, not yours. Trying again usually works.
      </p>
      <div className="mt-6">
        <Button type="button" onClick={retry} icon={<ArrowClockwise size={16} />}>
          Try again
        </Button>
      </div>
      {error.digest ? (
        <p className="mt-6 text-[11px] text-[var(--text-muted)]">
          Reference: {error.digest}
        </p>
      ) : null}
    </div>
  );
}

export default RouteError;
