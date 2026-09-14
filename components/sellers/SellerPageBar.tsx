import Link from "next/link";
import { ArrowLeft, UserCircle } from "@phosphor-icons/react/dist/ssr";

/**
 * The store page's phone bar: Figma "Group 455" (4218:2370) in "Seller Page -
 * Review", read 2026-09-14 — 72px of brand orange, a 28px ArrowLeft 16px in and
 * the 40px avatar on the right gutter. It replaces the site header below `md`,
 * the way the review page's bar does.
 *
 * NOT RENDERED: the frame's 28px "..." control. A store has no overflow actions
 * in this product (no follow, block or report for stores), and an empty menu
 * would be a control that does nothing.
 */
export function SellerPageBar() {
  return (
    <nav
      aria-label="Store"
      className="sticky top-0 z-30 flex h-[72px] items-center justify-between bg-[var(--accent-primary)] px-4 text-[var(--text-on-brand)] md:hidden"
    >
      <Link
        href="/search?tab=sellers"
        aria-label="Back to sellers"
        className="-ml-1.5 grid h-10 w-10 place-items-center rounded-full hover:bg-white/15"
      >
        <ArrowLeft size={28} />
      </Link>
      <Link
        href="/profile"
        aria-label="Your profile"
        className="grid h-10 w-10 place-items-center rounded-full hover:opacity-90"
      >
        <UserCircle size={40} weight="light" />
      </Link>
    </nav>
  );
}

export default SellerPageBar;
