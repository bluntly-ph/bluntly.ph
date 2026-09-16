import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CaretLeft, ChatCircle } from "@phosphor-icons/react/dist/ssr";

import { SellerFigures } from "@/components/sellers/SellerFigures";
import { SellerRatingSummary } from "@/components/sellers/SellerRatingSummary";
import { monthLabel, volumeBars } from "@/components/sellers/seller-model";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { Unavailable } from "@/components/site/Unavailable";
import { requireOnboardedUser } from "@/lib/dal";
import { getSellerDashboard, type SellerDashboard } from "@/lib/sellers";

export const metadata: Metadata = {
  title: "Store dashboard — bluntly",
};

const DATE = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeZone: "Asia/Manila" });

/**
 * Review monitoring for a store's approved owner (FR-4).
 *
 * No frame in the reference pack draws this, so it is built from the parts the
 * pack already defines — the rating card from the store page, a plain bar per
 * month, and the store's own questions — and it states only what the data
 * holds: counts per month, not trend arrows or percentages the numbers are too
 * thin to support.
 *
 * WEBSITE (`lg` and up): the store's standing sits in a column at the left and
 * the month bars and the questions waiting on the store read beside it, so an
 * owner sees the whole picture at once instead of scrolling a phone column.
 */
export default async function SellerDashboardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const me = await requireOnboardedUser();
  const result = await getSellerDashboard(id);
  if (!result.ok && result.reason === "not_found") notFound();

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url, role: me.role }} />
      <main className="mx-auto w-full max-w-[44rem] flex-1 px-6 py-8 lg:max-w-[72rem] lg:px-10 lg:py-10">
        <Link
          href={`/sellers/${id}`}
          className="inline-flex items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <CaretLeft size={16} /> Store page
        </Link>

        {result.ok ? (
          <Dashboard dashboard={result.dashboard} />
        ) : result.reason === "not_owner" ? (
          <div className="mt-6">
            <h1 className="text-[22px] font-bold text-[var(--text-primary)]">Store dashboard</h1>
            <p className="mt-2 text-[14px] text-[var(--text-secondary)]">
              Only the store&rsquo;s approved owner can see this. If you run this store, claim it from its
              page; a moderator checks every claim before anything changes.
            </p>
          </div>
        ) : (
          <Unavailable what="the store dashboard" />
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

function Dashboard({ dashboard }: { dashboard: SellerDashboard }) {
  const { seller, waiting_questions: waiting, unanswered_questions: unanswered } = dashboard;
  const bars = volumeBars(dashboard.monthly_volume);

  return (
    <>
      <p className="mt-6 text-[13px] text-[var(--text-secondary)]">Store dashboard</p>
      <h1 className="text-[22px] font-bold leading-snug text-[var(--text-primary)]">{seller.display_name}</h1>

      <div className="lg:grid lg:grid-cols-[24rem_minmax(0,1fr)] lg:items-start lg:gap-12">
        <div className="lg:sticky lg:top-24">
          <div className="mt-6">
            <SellerRatingSummary summary={seller.summary} />
          </div>
          {/* The FR-4 figures left the rating card for the store page's frame; the
          owner still needs them here. */}
          <div className="mt-5">
            <SellerFigures summary={seller.summary} />
          </div>
        </div>

        <div className="min-w-0">
          <section aria-labelledby="volume-heading" className="mt-10 lg:mt-6">
            <h2 id="volume-heading" className="text-[16px] font-semibold text-[var(--text-primary)]">
              Reviews per month
            </h2>
            <p className="mt-1 text-[12px] text-[var(--text-muted)]">
              Manila calendar months. Reviews a moderator removed are not counted.
            </p>
            <ul className="mt-4 flex flex-col gap-2">
              {bars.map((bar) => (
                <li key={bar.month} className="flex items-center gap-3 text-[13px]">
                  <span className="w-20 shrink-0 text-[var(--text-secondary)]">{monthLabel(bar.month)}</span>
                  <span className="h-3 flex-1 overflow-hidden rounded-full bg-[var(--base-gray-200)]">
                    <span
                      className="block h-full rounded-full bg-[var(--accent-success)]"
                      style={{ width: `${bar.share * 100}%` }}
                    />
                  </span>
                  <span className="w-8 shrink-0 text-right tabular-nums text-[var(--text-primary)]">
                    {bar.count}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="waiting-heading" className="mt-10">
            <h2 id="waiting-heading" className="text-[16px] font-semibold text-[var(--text-primary)]">
              Waiting on the store{unanswered > 0 ? ` (${unanswered})` : ""}
            </h2>
            <p className="mt-1 text-[12px] text-[var(--text-muted)]">
              Questions buyers asked this store that it has not answered yet, oldest first.
            </p>
            {waiting.length === 0 ? (
              <p className="mt-4 text-[14px] text-[var(--text-secondary)]">
                Nothing is waiting on the store.
              </p>
            ) : (
              <ul className="mt-4 border-t border-[var(--line-hairline-10)]">
                {waiting.map((q) => (
                  <li key={q.id} className="border-b border-[var(--line-hairline-10)]">
                    <Link href={`/questions/${q.id}`} className="flex items-start gap-3 py-4 no-underline">
                      <ChatCircle
                        size={18}
                        aria-hidden="true"
                        className="mt-0.5 shrink-0 text-[var(--accent-primary)]"
                      />
                      <span className="min-w-0">
                        <span className="block text-[14px] font-medium text-[var(--text-primary)]">
                          {q.body}
                        </span>
                        <span className="mt-0.5 block text-[12px] text-[var(--text-muted)]">
                          Asked <time dateTime={q.created_at}>{DATE.format(new Date(q.created_at))}</time>
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {unanswered > waiting.length ? (
              <p className="mt-3 text-[12px] text-[var(--text-muted)]">
                Showing the {waiting.length} that have waited longest.
              </p>
            ) : null}
          </section>
        </div>
      </div>
    </>
  );
}
