import type { Metadata } from "next";

import { RateSellerForm } from "@/components/sellers/RateSellerForm";
import { requireOnboardedUser } from "@/lib/dal";
import { getSeller } from "@/lib/sellers";

export const metadata: Metadata = {
  title: "Rate a seller — bluntly",
};

export default async function RateSellerPage({
  searchParams,
}: {
  searchParams: Promise<{ seller?: string }>;
}) {
  // Rating needs an account; this redirects to /login or /onboarding otherwise.
  const me = await requireOnboardedUser();
  const { seller: sellerId } = await searchParams;
  // "Rate this seller" on a store page arrives with the store already chosen,
  // so the composer opens on the rating step instead of asking again.
  const seller = sellerId ? await getSeller(sellerId) : null;

  return (
    // No SiteHeader, as on /reviews/new: the seller-review frames draw the
    // composer's own header, and only the form knows what "back" means. No
    // background of its own: the body's shows through, and the composer's
    // graph paper (ComposerGrid, -z-10) would be painted over by one.
    <div className="flex min-h-dvh flex-col">
      <RateSellerForm
        key={seller?.id ?? "find"}
        user={{ username: me.username, avatarUrl: me.avatar_url, role: me.role }}
        initialSeller={
          seller
            ? {
                id: seller.id,
                display_name: seller.display_name,
                platform: seller.platform,
                claim_status: seller.claim_status,
                review_count: seller.review_count,
              }
            : null
        }
      />
    </div>
  );
}
