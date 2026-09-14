import Link from "next/link";
import { ArrowLeft, UserCircle } from "@phosphor-icons/react/dist/ssr";

/**
 * The store page's phone bar: brand orange, 72px, a back arrow on the left and
 * the account on the right, as "Seller Page - Review.png" draws it. It replaces
 * the site header below `md`, the way the review page's bar does.
 *
 * NOT RENDERED: the frame's "..." control. A store has no overflow actions in
 * this product (no follow, block or report for stores), and an empty menu
 * would be a control that does nothing.
 */
export function SellerPageBar() {
  return (
    <nav
      aria-label="Store"
      className="sticky top-0 z-30 flex h-[72px] items-center justify-between bg-[var(--accent-primary)] px-4 text-white md:hidden"
    >
      <Link
        href="/search?tab=sellers"
        aria-label="Back to sellers"
        className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15"
      >
        <ArrowLeft size={26} />
      </Link>
      <Link
        href="/profile"
        aria-label="Your profile"
        className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15"
      >
        <UserCircle size={28} />
      </Link>
    </nav>
  );
}

export default SellerPageBar;
