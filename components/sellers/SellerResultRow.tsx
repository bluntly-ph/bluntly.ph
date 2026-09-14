import Link from "next/link";

import type { Seller } from "@/lib/sellers";

import { ClaimStatusLine, SellerAvatar, StarRow } from "./SellerIdentity";
import { PLATFORM_LABEL } from "./seller-model";

/**
 * A store as it appears in the Sellers tab of /search.
 *
 * Matched to "Mobile Search Page for Sellers.png": claim status, the store
 * name in bold, a count line, green stars, and the store's mark on the right.
 * Phone values from the frame: a 16px bold name, a 13px count line, 20px stars
 * about 6px apart, a 100px tile, 20px above and 16px below, and a 2px
 * full-bleed rule.
 *
 * NOT RENDERED, because no data behind it exists: "39 questions answered".
 * Store questions exist (0045) but no count of answered ones is served, so the
 * marketplace stands in its place. The stars are drawn only once the store has
 * a rating.
 */
export function SellerResultRow({ seller }: { seller: Seller }) {
  const count = seller.review_count;
  return (
    <li className="border-b-2 border-[var(--base-gray-150)] md:border-b md:border-[var(--line-hairline-10)]">
      <Link
        href={`/sellers/${seller.id}`}
        className="flex items-center gap-4 px-4 pb-4 pt-5 no-underline focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)] md:px-0 md:py-4"
      >
        <div className="min-w-0 flex-1">
          <ClaimStatusLine status={seller.claim_status} />
          <h2 className="mt-1 truncate text-[16px] font-bold text-[var(--text-primary)]">
            {seller.display_name}
          </h2>
          <p className="mt-0.5 text-[13px] text-[var(--text-primary)]">
            {count} {count === 1 ? "review" : "reviews"} • {PLATFORM_LABEL[seller.platform]}
          </p>
          {seller.overall_average !== null ? (
            <StarRow value={seller.overall_average} size={20} gap={6} className="mt-3" />
          ) : null}
        </div>
        <SellerAvatar name={seller.display_name} size={100} shape="tile" />
      </Link>
    </li>
  );
}

export default SellerResultRow;
