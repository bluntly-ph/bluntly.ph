import type { Metadata } from "next";
import Link from "next/link";
import { CheckCircle, Coins, Lightning } from "@phosphor-icons/react/dist/ssr";

import { PageShell } from "@/components/site/PageShell";
import { getUser } from "@/lib/dal";
import { benefitLines, bpsToPercent, getTiers, priorityLabel } from "@/lib/membership";

export const metadata: Metadata = {
  title: "Membership tiers — bluntly",
  description:
    "Special, Founding, and Standard membership on bluntly: what each tier earns you in affiliate revenue share and payout priority. Tiers are earned, never bought.",
};

export default async function MembershipPage() {
  // Both are defended: the page must render its explanation even signed-out or
  // with the API down, since it doubles as public documentation of the model.
  const [tiers, me] = await Promise.all([
    getTiers(),
    getUser().catch(() => null),
  ]);
  const myTier = me?.membership_tier ?? null;

  return (
    <PageShell width="wide">
      <h1 className="text-[32px] font-bold tracking-tight text-[var(--text-primary)]">
        Membership tiers
      </h1>
      <p className="mt-3 max-w-[46rem] text-[15px] leading-relaxed text-[var(--text-secondary)]">
        Your tier decides how much of the affiliate revenue from your reviews you
        keep, and how early you sit in the payout queue.{" "}
        <strong className="font-semibold text-[var(--text-primary)]">
          Tiers are earned, not bought.
        </strong>{" "}
        There is no subscription and nothing to pay for — everyone starts on
        Standard, and moderators assign the higher tiers.
      </p>

      {myTier ? (
        <p className="mt-4 inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-4 py-2 text-[13px] text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]">
          <CheckCircle size={16} weight="fill" className="text-[var(--accent-success)]" />
          You&rsquo;re on the{" "}
          <strong className="font-semibold capitalize text-[var(--text-primary)]">
            {myTier}
          </strong>{" "}
          tier
        </p>
      ) : null}

      {tiers.length > 0 ? (
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {tiers.map((tier) => {
            const mine = tier.code === myTier;
            const lines = benefitLines(tier.benefits);
            return (
              <section
                key={tier.id}
                aria-current={mine ? "true" : undefined}
                className={`flex flex-col rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-6 shadow-[var(--shadow-card)] ${
                  mine ? "ring-2 ring-[var(--accent-primary)]" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-[18px] font-semibold text-[var(--text-primary)]">
                    {tier.name}
                  </h2>
                  {mine ? (
                    <span className="rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-2.5 py-1 text-[11px] font-semibold text-white">
                      Your tier
                    </span>
                  ) : null}
                </div>

                <div className="mt-4 flex items-baseline gap-1.5">
                  <span className="text-[36px] font-bold leading-none text-[var(--text-primary)]">
                    {bpsToPercent(tier.revenue_share_bps)}
                  </span>
                  <span className="text-[13px] text-[var(--text-muted)]">
                    revenue share
                  </span>
                </div>

                <p className="mt-1 inline-flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)]">
                  <Lightning size={14} weight="fill" className="text-[var(--accent-star)]" />
                  {priorityLabel(tier.payout_priority)} for payouts
                </p>

                {tier.description ? (
                  <p className="mt-4 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                    {tier.description}
                  </p>
                ) : null}

                {lines.length > 0 ? (
                  <ul className="mt-4 flex flex-col gap-2 border-t border-[var(--border-subtle)] pt-4">
                    {lines.map((line) => (
                      <li
                        key={line}
                        className="flex items-start gap-2 text-[13px] text-[var(--text-secondary)]"
                      >
                        <CheckCircle
                          size={15}
                          weight="fill"
                          className="mt-0.5 shrink-0 text-[var(--accent-success)]"
                        />
                        {line}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
            );
          })}
        </div>
      ) : (
        <p className="mt-8 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-6 text-[13px] text-[var(--text-muted)] shadow-[var(--shadow-hairline-inset)]">
          Tier details are unavailable right now. Everyone still starts on
          Standard, and your earnings are unaffected.
        </p>
      )}

      <section className="mt-10 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-6 shadow-[var(--shadow-hairline-inset)]">
        <h2 className="inline-flex items-center gap-2 text-[16px] font-semibold text-[var(--text-primary)]">
          <Coins size={18} weight="fill" className="text-[var(--accent-star)]" />
          How you move up
        </h2>
        <p className="mt-2 text-[14px] leading-relaxed text-[var(--text-secondary)]">
          Tier is separate from your trust stage. Trust stage is your reputation
          as a reviewer and rises with verified, helpful reviews. Tier is a
          standing the team assigns — Founding recognises early reviewers who
          built the place, and Special is granted case by case. Neither can be
          purchased, and neither changes how your reviews are ranked or
          moderated.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            href="/dashboard"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-6 text-[14px] font-semibold text-white shadow-[var(--shadow-card)] transition-colors hover:bg-[var(--accent-primary-strong)]"
          >
            See your earnings
          </Link>
          <Link
            href="/how-it-works"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--surface-app)] px-6 text-[14px] font-semibold text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] transition-colors hover:text-[var(--accent-primary)]"
          >
            How bluntly works
          </Link>
        </div>
      </section>
    </PageShell>
  );
}
