import type { Metadata } from "next";
import Link from "next/link";
import { FileText } from "@phosphor-icons/react/dist/ssr";

import { ContractActions } from "@/components/dashboard/ContractActions";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { getContracts, daysUntil, hasOpenBuyout } from "@/lib/contracts";
import { requireOnboardedUser } from "@/lib/dal";

export const metadata: Metadata = {
  title: "Contracts — bluntly",
};

const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  expired: "Expired",
  bought_out: "Bought out",
};

const STATUS_STYLE: Record<string, string> = {
  active: "text-[var(--accent-success)]",
  expired: "text-[var(--text-muted)]",
  bought_out: "text-[var(--text-secondary)]",
};

export default async function ContractsPage() {
  const me = await requireOnboardedUser();
  const contracts = await getContracts();

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="mx-auto w-full max-w-[52rem] flex-1 px-6 py-8 lg:px-10 lg:py-10">
        <h1 className="text-[24px] font-bold text-[var(--text-primary)]">Contracts</h1>
        <p className="mt-1 max-w-[40rem] text-[14px] leading-relaxed text-[var(--text-secondary)]">
          One contract per monetized review. It starts by itself when a moderator
          attaches an affiliate link — there&rsquo;s nothing to sign up for. While
          a contract is active you earn your tier&rsquo;s share of the affiliate
          revenue from that review.
        </p>

        {contracts.length === 0 ? (
          <div className="mt-8 rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-6 py-10 text-center shadow-[var(--shadow-hairline-inset)]">
            <FileText size={28} className="mx-auto text-[var(--text-muted)]" />
            <p className="mt-3 text-[14px] text-[var(--text-primary)]">
              No contracts yet.
            </p>
            <p className="mt-1 text-[13px] text-[var(--text-muted)]">
              You&rsquo;ll get one when a review of yours is approved with an
              affiliate link.
            </p>
            <Link
              href="/reviews/new"
              className="mt-5 inline-flex h-10 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-5 text-[13px] font-semibold text-white transition-colors hover:bg-[var(--accent-primary-strong)]"
            >
              Write a review
            </Link>
          </div>
        ) : (
          <ul className="mt-6 flex flex-col gap-4">
            {contracts.map((c) => {
              const remaining = daysUntil(c.expires_at);
              const openBuyout = hasOpenBuyout(c);
              return (
                <li
                  key={c.id}
                  className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={`/reviews/${c.review_id}`}
                        className="text-[15px] font-semibold text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
                      >
                        {c.reviewTitle ?? "Your review"}
                      </Link>
                      <p className="mt-0.5 text-[12px] text-[var(--text-muted)]">
                        {c.term_months}-month term
                        {c.renewal_count > 0
                          ? ` · renewed ${c.renewal_count}×`
                          : ""}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 text-[12px] font-semibold ${STATUS_STYLE[c.status] ?? ""}`}
                    >
                      {STATUS_LABEL[c.status] ?? c.status}
                    </span>
                  </div>

                  <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
                    {c.status === "active"
                      ? remaining > 0
                        ? `Runs for another ${remaining} day${remaining === 1 ? "" : "s"}, until ${new Date(c.expires_at).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric" })}.`
                        : "Past its end date — renewal is being processed."
                      : c.status === "bought_out"
                        ? "Ended by buyout. This review no longer earns a revenue share."
                        : "Ended. This review no longer earns a revenue share."}
                  </p>

                  {c.status === "active" || openBuyout ? (
                    <ContractActions
                      contractId={c.id}
                      autoRenew={c.auto_renew}
                      buyoutAmount={openBuyout ? c.buyout_offer_amount : null}
                      isActive={c.status === "active"}
                    />
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}

        <div className="mt-8">
          <Link
            href="/dashboard"
            className="text-[13px] font-medium text-[var(--accent-primary)] hover:underline"
          >
            ← Back to earnings
          </Link>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
