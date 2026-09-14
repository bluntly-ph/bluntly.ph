import type { Metadata } from "next";
import Link from "next/link";

import { SellerClaimDecision } from "@/components/admin/SellerClaimDecision";
import { getPendingSellerClaims } from "@/lib/sellers";

export const metadata: Metadata = { title: "Sellers — bluntly admin" };

/**
 * Seller claims waiting for a moderator (FR-4).
 *
 * FR-4 limits seller verification to cross-checking the store name against the
 * public marketplace listing, so that is the instruction on the screen, and
 * the claimant's own evidence is shown in full beside the store it names.
 * Removing a seller review happens on the store's page, where the review is
 * read in context; a moderator sees a remove control there.
 */
export default async function SellersAdminPage() {
  const claims = await getPendingSellerClaims();

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 pb-3">
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Seller claims</h2>
        <p className="mt-1 max-w-[52rem] text-[13px] text-[var(--text-secondary)]">
          {claims
            ? `${claims.length} claim${claims.length === 1 ? "" : "s"} waiting, oldest first.`
            : "Unable to load seller claims right now."}{" "}
          Approve only when the store name on the public marketplace listing matches the
          claimant&rsquo;s evidence. Approval marks the store as claimed and stops its owner rating
          it. You cannot decide a claim you submitted.
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)]">
        <table className="w-full min-w-[46rem] border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-[var(--surface-app)]">
            <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
              <th className="px-4 py-3 font-medium">Store</th>
              <th className="px-4 py-3 font-medium">Evidence</th>
              <th className="px-4 py-3 font-medium">Submitted</th>
              <th className="px-4 py-3 font-medium">Decision</th>
            </tr>
          </thead>
          <tbody>
            {!claims || claims.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-12 text-center text-[13px] text-[var(--text-secondary)]">
                  {claims ? "No claims waiting." : "Unable to load seller claims."}
                </td>
              </tr>
            ) : (
              claims.map((claim) => (
                <tr key={claim.id} className="border-t border-[var(--border-subtle)] align-top text-[13px]">
                  <td className="px-4 py-3">
                    <Link
                      href={`/sellers/${claim.seller_id}`}
                      className="font-medium text-[var(--text-primary)] underline hover:text-[var(--accent-primary)]"
                    >
                      {claim.seller_display_name ?? "Unnamed store"}
                    </Link>
                  </td>
                  <td className="max-w-[28rem] whitespace-pre-line break-words px-4 py-3 text-[var(--text-secondary)]">
                    {claim.evidence ?? "No evidence given."}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-[12px] text-[var(--text-muted)]">
                    {new Date(claim.created_at).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                  </td>
                  <td className="px-4 py-3">
                    <SellerClaimDecision
                      claimId={claim.id}
                      sellerName={claim.seller_display_name ?? "this store"}
                    />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
