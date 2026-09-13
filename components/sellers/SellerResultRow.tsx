import Link from "next/link";

import type { Seller } from "@/lib/sellers";

import { ClaimStatusLine, SellerAvatar, StarRow } from "./SellerIdentity";
import { PLATFORM_LABEL } from "./seller-model";

/**
 * A store as it appears in the Sellers tab of /search.
 *
 * Matched to "Mobile Search Page for Sellers.png": claim status, the store
 * name in bold, a count line, green stars, and the store's mark on the right.
 *
 * NOT RENDERED, because no data behind it exists: "39 questions answered".
 * Seller Q&A is not linked to stores yet, so the count would be invented.
 * The stars are drawn only once the store has a rating.
 */
export function SellerResultRow({ seller }: { seller: Seller }) {
  const count = seller.review_count;
  return (
    <li className="border-b border-[var(--line-hairline-10)]">
      <Link
        href={`/sellers/${seller.id}`}
        className="flex items-center gap-4 py-4 no-underline focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
      >
        <div className="min-w-0 flex-1">
          <ClaimStatusLine status={seller.claim_status} />
          <h2 className="mt-1 truncate text-[15px] font-bold text-[var(--text-primary)]">
            {seller.display_name}
          </h2>
          <p className="mt-0.5 text-[13px] text-[var(--text-secondary)]">
            {count} {count === 1 ? "review" : "reviews"} · {PLATFORM_LABEL[seller.platform]}
          </p>
          {seller.overall_average !== null ? (
            <StarRow value={seller.overall_average} size={22} className="mt-2" />
          ) : null}
        </div>
        <SellerAvatar name={seller.display_name} size={100} shape="tile" />
      </Link>
    </li>
  );
}

export default SellerResultRow;
