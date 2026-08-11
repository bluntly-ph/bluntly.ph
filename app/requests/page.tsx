import type { Metadata } from "next";
import Link from "next/link";
import { Coins, PlusCircle } from "@phosphor-icons/react/dist/ssr";

import { RequestUpvote } from "@/components/requests/RequestUpvote";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { Button } from "@/components/ui/Button";
import { getUser } from "@/lib/dal";
import { getRequests } from "@/lib/requests";

export const metadata: Metadata = {
  title: "Requests — bluntly",
};

export default async function RequestsPage() {
  // Parallel: the viewer and the board are independent (see app/page.tsx).
  const [me, requests] = await Promise.all([
    getUser().catch(() => null),
    getRequests("reward"),
  ]);
  const user: HeaderUser = me
    ? { username: me.username, avatarUrl: me.avatar_url }
    : null;
  const canVote = me !== null;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto w-full max-w-[52rem] flex-1 px-6 py-8 lg:py-10">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
              Review requests
            </h1>
            <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
              Can&rsquo;t find a review? Put up a bounty and the community will write one.
            </p>
          </div>
          <Link href="/requests/new" className="contents">
            <Button size="sm" icon={<PlusCircle size={16} weight="fill" />}>
              Post a request
            </Button>
          </Link>
        </div>

        {requests.length > 0 ? (
          <ul className="mt-6 flex flex-col gap-3">
            {requests.map((r) => (
              <li
                key={r.id}
                className="flex gap-4 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)]"
              >
                <RequestUpvote requestId={r.id} count={r.upvote_count} canVote={canVote} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
                      {r.title}
                    </h2>
                    <span className="inline-flex items-center gap-1 rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--accent-star)_18%,transparent)] px-2 py-0.5 text-[12px] font-semibold text-[var(--base-ink-700)]">
                      <Coins size={13} weight="fill" className="text-[var(--accent-star)]" />
                      {r.effective_reward}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-[13px] text-[var(--text-secondary)]">
                    {r.details}
                  </p>
                  <div className="mt-2">
                    <Link
                      href="/reviews/new"
                      className="text-[13px] font-medium text-[var(--accent-primary)] hover:underline"
                    >
                      Answer with a review →
                    </Link>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="mt-6 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-10 text-center shadow-[var(--shadow-hairline-inset)]">
            <p className="text-[15px] font-semibold text-[var(--text-primary)]">
              No open requests
            </p>
            <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
              Be the first to ask the community for a review.
            </p>
          </div>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}
