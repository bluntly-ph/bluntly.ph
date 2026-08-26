import type { Metadata } from "next";
import Link from "next/link";

import { DashboardScreen, HeroAmount } from "@/components/dashboard/DashboardScreen";
import { PayoutAccountForm } from "@/components/dashboard/PayoutAccountForm";
import { requireOnboardedUser } from "@/lib/dal";
import { getDashboard, PAYOUT_MIN_PHP, peso } from "@/lib/dashboard";

export const metadata: Metadata = { title: "Transfer — bluntly" };

/**
 * Transfer, built to frame 5762:332.
 *
 * The frame shows a balance and a `Request Withdrawal` button. It also shows
 * ₱328.04, which is sample data — the real wallet is rendered instead, because
 * a Figma value on a money screen is the one thing that must never be
 * hardcoded.
 *
 * Below the button the frame's sheet is empty, so the sheet carries the
 * functionality the button needs to be honest about: the ₱300 threshold, how
 * far off it is, and the payout account. That is existing, signed behaviour,
 * not new scope.
 */
export default async function TransferPage() {
  const me = await requireOnboardedUser();
  const { balance } = await getDashboard();
  const wallet = balance ? Number(balance.wallet_balance) : 0;
  const eligible = wallet >= PAYOUT_MIN_PHP;
  const remaining = Math.max(PAYOUT_MIN_PHP - wallet, 0);

  return (
    <DashboardScreen
      heroHeight={510}
      hero={
        <HeroAmount label="Est. Comm" amount={peso(wallet)}>
          {/* Disabled rather than hidden when under the threshold: the frame
              has this control, and a reviewer needs to see that withdrawal
              exists and why it is not available yet. */}
          <button
            type="button"
            disabled={!eligible}
            aria-describedby={eligible ? undefined : "withdrawal-threshold"}
            className="mt-6 inline-flex items-center justify-center rounded-[var(--radius-pill)] bg-white px-6 py-2.5 text-[13px] font-semibold text-[var(--text-primary)] shadow-[var(--shadow-card)] transition-opacity focus-visible:outline focus-visible:outline-2 focus-visible:outline-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            Request Withdrawal
          </button>
          {!eligible ? (
            <p id="withdrawal-threshold" className="mt-3 text-[12px] text-white/85">
              {peso(remaining)} more to reach the {peso(PAYOUT_MIN_PHP)} minimum
            </p>
          ) : null}
        </HeroAmount>
      }
    >
      <div className="px-4 pb-12">
        <section aria-labelledby="threshold-heading">
          <h2 id="threshold-heading" className="text-[15px] font-semibold text-[var(--text-primary)]">
            Payout threshold
          </h2>
          <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
            Withdrawals open at {peso(PAYOUT_MIN_PHP)}. Your balance is{" "}
            {peso(wallet)}.
          </p>
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={PAYOUT_MIN_PHP}
            aria-valuenow={Math.min(wallet, PAYOUT_MIN_PHP)}
            aria-label="Progress toward the payout minimum"
            className="mt-3 h-2 overflow-hidden rounded-[var(--radius-pill)] bg-[var(--surface-card)]"
          >
            <div
              className="h-full rounded-[var(--radius-pill)] bg-[var(--accent-primary)]"
              style={{ width: `${Math.min(wallet / PAYOUT_MIN_PHP, 1) * 100}%` }}
            />
          </div>
        </section>

        <section aria-labelledby="account-heading" className="mt-8">
          <h2 id="account-heading" className="text-[15px] font-semibold text-[var(--text-primary)]">
            Where the money goes
          </h2>
          <div className="mt-3">
            <PayoutAccountForm />
          </div>
        </section>

        <p className="mt-8 text-[12px] text-[var(--text-muted)]">
          Signed in as {me.username ?? me.display_name}.{" "}
          <Link href="/dashboard/history" className="underline hover:text-[var(--accent-primary)]">
            See your earnings history
          </Link>
        </p>
      </div>
    </DashboardScreen>
  );
}
