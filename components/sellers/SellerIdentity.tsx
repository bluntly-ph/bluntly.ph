import { SealCheck, Star } from "@phosphor-icons/react/dist/ssr";

import { sellerInitials } from "./seller-model";

/**
 * The small pieces every seller surface shares: the store's mark, whether it
 * has been claimed, and a row of stars.
 *
 * No hooks, so server pages and the client composer both use them.
 */

const FACE = "font-[family-name:var(--font-system)]";

/**
 * A store has no logo in this product. The owner's frames draw the unclaimed
 * store ("JAS") as its initials on a plain disc, so every store is drawn that
 * way rather than with a borrowed or invented logo.
 */
export function SellerAvatar({
  name,
  size = 80,
  shape = "circle",
}: {
  name: string;
  size?: number;
  shape?: "circle" | "tile";
}) {
  return (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-center bg-[var(--surface-card)] ${FACE} text-[var(--text-muted)] shadow-[var(--shadow-hairline-inset)] ${
        shape === "circle" ? "rounded-full" : "rounded-[var(--radius-md)]"
      }`}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.28) }}
    >
      {sellerInitials(name)}
    </span>
  );
}

/**
 * "Claimed Profile" only after a moderator approved a claim; everything else,
 * including a store with a claim still waiting, is unclaimed.
 */
export function ClaimStatusLine({ status }: { status: string }) {
  const claimed = status === "claimed";
  return (
    <span className={`flex items-center gap-1 ${FACE} text-[13px] text-[var(--text-muted)]`}>
      {claimed ? <SealCheck size={16} aria-hidden="true" /> : null}
      {claimed ? "Claimed Profile" : "Unclaimed Profile"}
    </span>
  );
}

/** Display only. A store with no rating draws grey stars and says so. */
export function StarRow({
  value,
  size = 20,
  className = "",
}: {
  value: number | null;
  size?: number;
  className?: string;
}) {
  const filled = value === null ? 0 : Math.round(value);
  return (
    <span
      role="img"
      aria-label={value === null ? "Not rated yet" : `Rated ${value} out of 5`}
      className={`inline-flex gap-[2px] ${className}`}
    >
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          size={size}
          weight="fill"
          aria-hidden="true"
          className={n <= filled ? "text-[var(--accent-success)]" : "text-[var(--base-gray-300)]"}
        />
      ))}
    </span>
  );
}
