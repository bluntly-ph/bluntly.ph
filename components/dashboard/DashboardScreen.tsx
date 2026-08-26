import Image from "next/image";
import Link from "next/link";
import { ArrowLeft } from "@phosphor-icons/react/dist/ssr";

/**
 * The chrome every dashboard sub-screen shares.
 *
 * Transfer (5762:332), History (5762:472) and Reviews (6159:1510) all open the
 * same way: a 72px nav carrying a back arrow and the Contributor pill, an
 * orange hero, then a white sheet with a rounded top edge. Building it once
 * means the four screens cannot drift apart from each other, which is the
 * failure the entry frame already had when its hero was an absolutely
 * positioned overlay.
 *
 * `heroHeight` is the frame's own hero depth. It differs per screen — 510 on
 * Transfer, shallower on History — so it is a prop rather than a constant.
 */
export function DashboardScreen({
  backHref = "/dashboard",
  hero,
  heroHeight = 402,
  children,
}: {
  backHref?: string;
  hero: React.ReactNode;
  heroHeight?: number;
  children?: React.ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-[430px] lg:max-w-[46rem]">
      <div
        className="relative"
        style={{
          background:
            "linear-gradient(160deg, var(--accent-primary) 0%, var(--accent-strong, #c2410c) 100%)",
        }}
      >
        <div className="flex h-[72px] items-center justify-between px-6">
          <Link
            href={backHref}
            aria-label="Back"
            className="-ml-1 rounded-full p-1 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
          >
            <ArrowLeft size={28} weight="regular" />
          </Link>
          <span className="inline-flex h-8 items-center gap-2 rounded-[var(--radius-pill)] bg-white pl-3 pr-4">
            <Image src="/icon.svg" alt="" width={16} height={16} className="h-4 w-4" />
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              Contributor
            </span>
          </span>
        </div>

        <div style={{ minHeight: `${Math.max(heroHeight - 72, 0)}px` }}>{hero}</div>
      </div>

      {/* The frame's white sheet, pulled up over the hero's foot so its rounded
          top edge reads as the sheet sitting on the gradient rather than as a
          gap between two blocks. */}
      <div className="relative -mt-8 min-h-[40vh] rounded-t-[28px] bg-[var(--surface-app)] pt-6">
        {children}
      </div>
    </div>
  );
}

/** The centred "Est. Comm" + amount the Transfer and entry frames both show. */
export function HeroAmount({
  label,
  amount,
  children,
}: {
  label: string;
  amount: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="pb-10 pt-6 text-center">
      <p className="text-[13px] font-medium text-white/80">{label}</p>
      <p className="mt-1 text-[40px] font-bold leading-tight text-white [font-variant-numeric:tabular-nums]">
        {amount}
      </p>
      {children}
    </div>
  );
}
