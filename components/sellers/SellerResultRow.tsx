import Link from "next/link";
import { DotOutline } from "@phosphor-icons/react/dist/ssr";

import type { Seller } from "@/lib/sellers";

import { ClaimStatusLine, SellerAvatar, StarRow } from "./SellerIdentity";
import { PLATFORM_LABEL } from "./seller-model";

/**
 * A store in the Sellers tab of /search: Figma "SellerPreviewCard" (7159:4873),
 * as placed in "Mobile Search Page for Sellers" (3954:650). Read 2026-09-14.
 *
 * Phone values from the component: a 222px body and a 100px white media tile
 * pushed apart; the claim badge, 8px down to the store in 14px Poppins Bold,
 * 4px down to the counts in 12px Light split by a 12px DotOutline, then 16px
 * down to five 20px stars 4px apart. 20px above, 16px below, a 1px rule.
 *
 * INTENTIONAL PRODUCT DIFFERENCES: "39 questions answered" is not served —
 * store questions exist (0045) but no count of answered ones — so the
 * marketplace stands in its place. Stores carry no logo, so the tile shows the
 * store's initials. The stars are drawn only once the store has a rating.
 */
export function SellerResultRow({ seller }: { seller: Seller }) {
  const count = seller.review_count;
  return (
    <li className="border-b border-[var(--line-hairline-10)]">
      <Link
        href={`/sellers/${seller.id}`}
        className="flex items-start justify-between gap-4 px-4 pb-4 pt-5 text-[var(--text-primary)] no-underline focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)] md:px-0 md:py-4"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-4 max-md:max-w-[222px]">
          <div className="flex flex-col gap-2">
            <ClaimStatusLine status={seller.claim_status} />
            <div className="flex flex-col gap-1">
              <h2 className="truncate text-[14px] font-bold leading-[21px]">{seller.display_name}</h2>
              <p className="flex items-center gap-[3px] text-[12px] font-light leading-none">
                {count} {count === 1 ? "review" : "reviews"}
                <DotOutline size={12} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
                {PLATFORM_LABEL[seller.platform]}
              </p>
            </div>
          </div>
          {seller.overall_average !== null ? (
            <StarRow value={seller.overall_average} size={20} gap={4} />
          ) : null}
        </div>
        <SellerAvatar name={seller.display_name} size={100} shape="tile" />
      </Link>
    </li>
  );
}

export default SellerResultRow;
