import type { Metadata } from "next";
import Link from "next/link";
import { PlusCircle, Users } from "@phosphor-icons/react/dist/ssr";

import { RequestUpvote } from "@/components/requests/RequestUpvote";
import { SiteFooter } from "@/components/site/SiteFooter";
import { Unavailable } from "@/components/site/Unavailable";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { Button } from "@/components/ui/Button";
import { getUser } from "@/lib/dal";
import { getRequests } from "@/lib/requests";
import { getSessionToken } from "@/lib/session";

export const metadata: Metadata = {
  title: "Requests — bluntly",
};

export default async function RequestsPage() {
  // The cookie read is local, so the token costs nothing before the network work.
  const token = await getSessionToken();
  // Parallel: the viewer and the board are independent (see app/page.tsx).
  const [me, requests] = await Promise.all([
    getUser().catch(() => null),
    // Token passed so each row knows whether this viewer already up-voted it
    // (BUG-026); anonymous readers get the same board with my_upvote false.
    getRequests("demand", token),
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
              Can&rsquo;t find a review? Ask for one — up-votes push the most
              wanted questions to the top.
            </p>
          </div>
          <Link href="/requests/new" className="contents">
            <Button size="sm" icon={<PlusCircle size={16} weight="fill" />}>
              Post a request
            </Button>
          </Link>
        </div>

        {requests === null ? (
          <Unavailable what="the request board" />
        ) : requests.length > 0 ? (
          <ul className="mt-6 flex flex-col gap-3">
            {requests.map((r) => (
              <li
                key={r.id}
                className="flex gap-4 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)]"
              >
                <RequestUpvote
                  requestId={r.id}
                  count={r.upvote_count}
                  canVote={canVote}
                  myUpvote={r.my_upvote}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
                      {r.title}
                    </h2>
                    {/* Demand, not a purse. The badge showed a token reward
                        until that economy was retired; how many people are
                        waiting on the answer is the useful signal for a
                        reviewer deciding what to write next. */}
                    {r.upvote_count > 0 ? (
                      <span className="inline-flex items-center gap-1 rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--accent-primary)_12%,transparent)] px-2 py-0.5 text-[12px] font-medium text-[var(--accent-primary)]">
                        <Users size={13} weight="fill" />
                        {r.upvote_count} waiting
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 line-clamp-2 text-[13px] text-[var(--text-secondary)]">
                    {r.details}
                  </p>
                  <div className="mt-1">
                    {/* Same -my/py hit-area trick as the header and footer
                        links: the text is 19px tall, which fails WCAG 2.5.8.
                        This one only surfaces when the board has a request, so
                        the a11y spec missed it while the board was empty. */}
                    <Link
                      href="/reviews/new"
                      className="-my-2.5 inline-flex items-center py-2.5 text-[13px] font-medium text-[var(--accent-primary)] hover:underline"
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
