import type { Metadata } from "next";
import Link from "next/link";
import { Coins, Wallet } from "@phosphor-icons/react/dist/ssr";

import { PayoutAccountForm } from "@/components/dashboard/PayoutAccountForm";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { Button } from "@/components/ui/Button";
import { requireUser } from "@/lib/dal";
import { getDashboard, PAYOUT_MIN_PHP, peso } from "@/lib/dashboard";

export const metadata: Metadata = {
  title: "Earnings — bluntly",
};

const KIND_LABELS: Record<string, string> = {
  earn_review_published: "Review published",
  earn_commission: "Affiliate commission",
  earn_request_reward: "Request reward",
  spend_request_escrow: "Request bounty escrowed",
  refund_request_escrow: "Bounty refunded",
  admin_grant: "Admin grant",
  admin_deduct: "Admin deduction",
  platform_topup: "Platform top-up",
  adjustment: "Adjustment",
};

const label = (kind: string) =>
  KIND_LABELS[kind] ?? kind.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

const STATUS_STYLE: Record<string, string> = {
  paid: "text-[var(--accent-success)]",
  processing: "text-[var(--accent-star)]",
  scheduled: "text-[var(--text-secondary)]",
  failed: "text-[var(--accent-danger)]",
  cancelled: "text-[var(--text-muted)]",
};

export default async function DashboardPage() {
  const me = await requireUser();
  const { balance, transactions, payouts } = await getDashboard();

  const wallet = balance ? Number(balance.wallet_balance) : 0;
  const canPayout = wallet >= PAYOUT_MIN_PHP;
  const progress = Math.min(wallet / PAYOUT_MIN_PHP, 1) * 100;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="mx-auto w-full max-w-[64rem] flex-1 px-6 py-8 lg:px-10 lg:py-10">
        <h1 className="text-[24px] font-bold text-[var(--text-primary)]">Earnings</h1>
        <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
          Your affiliate earnings and Honesty Fund share, paid out via PayPal.
        </p>

        {/* Balance cards */}
        <section className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] p-6 text-[var(--base-gray-100)] shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2 text-[13px] opacity-90">
              <Wallet size={18} weight="fill" /> Wallet balance
            </div>
            <div className="mt-2 text-[32px] font-bold">
              {balance ? peso(balance.wallet_balance) : "₱0.00"}
            </div>
          </div>
          <div className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-6 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2 text-[13px] text-[var(--text-secondary)]">
              <Coins size={18} weight="fill" className="text-[var(--accent-star)]" /> Tokens
            </div>
            <div className="mt-2 text-[32px] font-bold text-[var(--text-primary)]">
              {balance?.token_balance ?? 0}
            </div>
          </div>
        </section>

        {/* Payout */}
        <section className="mt-6 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-6 shadow-[var(--shadow-card)]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">Payouts</h2>
            <Button size="sm" disabled={!canPayout}>
              {canPayout ? "Request payout" : `₱${PAYOUT_MIN_PHP} to withdraw`}
            </Button>
          </div>
          {!canPayout ? (
            <>
              <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-[var(--base-gray-150)]">
                <span
                  className="block h-full rounded-full bg-[var(--accent-primary)]"
                  style={{ width: `${Math.max(progress, 4)}%` }}
                />
              </div>
              <p className="mt-2 text-[12px] text-[var(--text-muted)]">
                {peso(wallet)} of ₱{PAYOUT_MIN_PHP} minimum
              </p>
            </>
          ) : null}
          <div className="mt-5 border-t border-[var(--border-subtle)] pt-4">
            <p className="text-[13px] font-medium text-[var(--text-primary)]">
              Where should we send your payouts?
            </p>
            <div className="mt-2">
              <PayoutAccountForm />
            </div>
          </div>
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          {/* Transactions */}
          <section>
            <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
              Recent activity
            </h2>
            <ul className="mt-3 flex flex-col divide-y divide-[var(--border-subtle)] rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 shadow-[var(--shadow-hairline-inset)]">
              {transactions.length > 0 ? (
                transactions.map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3 py-3">
                    <div>
                      <p className="text-[13px] font-medium text-[var(--text-primary)]">
                        {label(t.kind)}
                      </p>
                      {t.note ? (
                        <p className="text-[12px] text-[var(--text-muted)]">{t.note}</p>
                      ) : null}
                    </div>
                    <span
                      className={`text-[14px] font-semibold ${t.amount >= 0 ? "text-[var(--accent-success)]" : "text-[var(--text-secondary)]"}`}
                    >
                      {t.amount >= 0 ? "+" : ""}
                      {t.amount}
                    </span>
                  </li>
                ))
              ) : (
                <li className="py-8 text-center text-[13px] text-[var(--text-muted)]">
                  No activity yet — publish a review to start earning.
                </li>
              )}
            </ul>
          </section>

          {/* Payouts history */}
          <section>
            <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
              Payout history
            </h2>
            <ul className="mt-3 flex flex-col divide-y divide-[var(--border-subtle)] rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 shadow-[var(--shadow-hairline-inset)]">
              {payouts.length > 0 ? (
                payouts.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-3 py-3">
                    <div>
                      <p className="text-[13px] font-medium text-[var(--text-primary)]">
                        {peso(p.amount)}
                      </p>
                      <p className="text-[12px] text-[var(--text-muted)]">
                        {new Date(p.scheduled_for).toLocaleDateString("en-PH")}
                      </p>
                    </div>
                    <span
                      className={`text-[12px] font-medium capitalize ${STATUS_STYLE[p.status] ?? "text-[var(--text-secondary)]"}`}
                    >
                      {p.status}
                    </span>
                  </li>
                ))
              ) : (
                <li className="py-8 text-center text-[13px] text-[var(--text-muted)]">
                  No payouts yet.
                </li>
              )}
            </ul>
          </section>
        </div>

        <div className="mt-8">
          <Link href="/reviews/new" className="contents">
            <Button>Write a review &amp; earn</Button>
          </Link>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
