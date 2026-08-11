import type { Metadata } from "next";
import Link from "next/link";
import { Info, SealCheck, Wallet } from "@phosphor-icons/react/dist/ssr";

import { PayoutAccountForm } from "@/components/dashboard/PayoutAccountForm";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { Button } from "@/components/ui/Button";
import { requireOnboardedUser } from "@/lib/dal";
import { getDashboard, PAYOUT_MIN_PHP, peso } from "@/lib/dashboard";
import { bpsToPercent, getTiers } from "@/lib/membership";

export const metadata: Metadata = {
  title: "Earnings — bluntly",
};

const STATUS_STYLE: Record<string, string> = {
  paid: "text-[var(--accent-success)]",
  processing: "text-[var(--accent-star)]",
  scheduled: "text-[var(--text-secondary)]",
  failed: "text-[var(--accent-danger)]",
  cancelled: "text-[var(--text-muted)]",
};

/** Why a payout sits in each state, in the reviewer's words rather than the scheduler's. */
const STATUS_NOTE: Record<string, string> = {
  scheduled: "Reserved from your wallet, waiting for the next batch.",
  processing: "Sent to PayPal — settling now.",
  paid: "Landed in your PayPal account.",
  failed: "Didn't go through. The amount was returned to your wallet.",
  cancelled: "Called off. The amount was returned to your wallet.",
};

export default async function DashboardPage() {
  const me = await requireOnboardedUser();
  const [{ balance, payouts }, tiers] = await Promise.all([
    getDashboard(),
    getTiers(),
  ]);

  const wallet = balance ? Number(balance.wallet_balance) : 0;
  const atMinimum = wallet >= PAYOUT_MIN_PHP;
  const progress = Math.min(wallet / PAYOUT_MIN_PHP, 1) * 100;
  const myTier = tiers.find((t) => t.code === me.membership_tier) ?? null;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="mx-auto w-full max-w-[64rem] flex-1 px-6 py-8 lg:px-10 lg:py-10">
        <h1 className="text-[24px] font-bold text-[var(--text-primary)]">Earnings</h1>
        <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
          Your affiliate earnings and Honesty Fund share, paid out via PayPal.
        </p>

        <section className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] p-6 text-[var(--base-gray-100)] shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2 text-[13px] opacity-90">
              <Wallet size={18} weight="fill" /> Wallet balance
            </div>
            <div className="mt-2 text-[32px] font-bold">
              {balance ? peso(balance.wallet_balance) : "₱0.00"}
            </div>
            <p className="mt-1 text-[12px] opacity-80">
              Available to be paid out
            </p>
          </div>

          {/* Tier, not tokens: the tier is what actually determines the reviewer's
              cut and their place in the payout queue. */}
          <Link
            href="/membership"
            className="group rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-6 shadow-[var(--shadow-card)] transition-shadow hover:shadow-[var(--shadow-fab)]"
          >
            <div className="flex items-center gap-2 text-[13px] text-[var(--text-secondary)]">
              <SealCheck size={18} weight="fill" className="text-[var(--accent-primary)]" />
              Membership tier
            </div>
            <div className="mt-2 text-[32px] font-bold capitalize text-[var(--text-primary)]">
              {myTier?.name ?? me.membership_tier}
            </div>
            <p className="mt-1 text-[12px] text-[var(--text-muted)] group-hover:text-[var(--accent-primary)]">
              {myTier
                ? `You keep ${bpsToPercent(myTier.revenue_share_bps)} of affiliate revenue`
                : "See what your tier earns you"}
            </p>
          </Link>
        </section>

        <section className="mt-6 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-6 shadow-[var(--shadow-card)]">
          <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">Payouts</h2>

          {/* Payouts are scheduler-driven, not user-requested: the batch job picks
              up everyone at or above the minimum with a payout account set, in
              tier-priority order. There is deliberately no "request" button — it
              would imply a control the reviewer does not have. */}
          <p className="mt-2 flex items-start gap-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">
            <Info size={16} className="mt-0.5 shrink-0 text-[var(--text-muted)]" />
            <span>
              Payouts run automatically. Once your wallet reaches{" "}
              <strong className="font-semibold text-[var(--text-primary)]">
                ₱{PAYOUT_MIN_PHP}
              </strong>{" "}
              and you&rsquo;ve set a PayPal account below, you&rsquo;re included in
              the next batch — higher tiers are paid first.
            </span>
          </p>

          {!atMinimum ? (
            <>
              <div
                role="progressbar"
                aria-valuenow={Math.round(wallet)}
                aria-valuemin={0}
                aria-valuemax={PAYOUT_MIN_PHP}
                aria-label="Progress to payout minimum"
                className="mt-4 h-2 w-full overflow-hidden rounded-full bg-[var(--base-gray-150)]"
              >
                <span
                  className="block h-full rounded-full bg-[var(--accent-primary)]"
                  style={{ width: `${Math.max(progress, 4)}%` }}
                />
              </div>
              <p className="mt-2 text-[12px] text-[var(--text-muted)]">
                {peso(wallet)} of ₱{PAYOUT_MIN_PHP} minimum
              </p>
            </>
          ) : (
            <p className="mt-3 text-[13px] font-medium text-[var(--accent-success)]">
              You&rsquo;re over the minimum — you&rsquo;ll be included in the next
              batch.
            </p>
          )}

          <div className="mt-5 border-t border-[var(--border-subtle)] pt-4">
            <p className="text-[13px] font-medium text-[var(--text-primary)]">
              Where should we send your payouts?
            </p>
            <div className="mt-2">
              <PayoutAccountForm />
            </div>
          </div>
        </section>

        <section className="mt-6">
          <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
            Payment history
          </h2>
          <ul className="mt-3 flex flex-col divide-y divide-[var(--border-subtle)] rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 shadow-[var(--shadow-hairline-inset)]">
            {payouts.length > 0 ? (
              payouts.map((p) => (
                <li
                  key={p.id}
                  className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-3"
                >
                  <div className="min-w-0">
                    <p className="text-[14px] font-semibold text-[var(--text-primary)]">
                      {peso(p.amount)}
                      <span className="ml-1.5 text-[12px] font-normal text-[var(--text-muted)]">
                        {p.currency}
                      </span>
                    </p>
                    <p className="text-[12px] text-[var(--text-muted)]">
                      {STATUS_NOTE[p.status] ?? ""}
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`text-[12px] font-medium capitalize ${STATUS_STYLE[p.status] ?? "text-[var(--text-secondary)]"}`}
                    >
                      {p.status}
                    </span>
                    <p className="text-[12px] text-[var(--text-muted)]">
                      {new Date(p.paid_at ?? p.scheduled_for).toLocaleDateString(
                        "en-PH",
                        { year: "numeric", month: "short", day: "numeric" },
                      )}
                    </p>
                  </div>
                </li>
              ))
            ) : (
              <li className="py-8 text-center text-[13px] text-[var(--text-muted)]">
                No payouts yet — publish a review to start earning.
              </li>
            )}
          </ul>
        </section>

        <div className="mt-8 flex flex-wrap items-center gap-4">
          <Link href="/reviews/new" className="contents">
            <Button>Write a review &amp; earn</Button>
          </Link>
          <Link
            href="/contracts"
            className="text-[13px] font-medium text-[var(--accent-primary)] hover:underline"
          >
            View your contracts →
          </Link>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
