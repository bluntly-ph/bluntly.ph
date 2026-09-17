import type { Metadata } from "next";
import Link from "next/link";
import { FeedCard } from "@/components/feed/FeedCard";
import { BrowseLayout, RAIL_LABEL, TakePartGroup } from "@/components/site/BrowseRails";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { INTERESTS } from "@/lib/interests";
import { getUser } from "@/lib/dal";
import { getFeed } from "@/lib/reviews";
import { getSessionToken } from "@/lib/session";
import { firstImageIndex, listImageHints } from "@/lib/list-image-hints";

export const metadata: Metadata = {
  title: "Feed — bluntly",
  description: "Honest product reviews from the bluntly community.",
};

const PAGE_SIZE = 12;

/**
 * The browsing surface.
 *
 * `/` stays the landing page — it argues for the platform to someone who has
 * not decided yet. This is the page for someone who already has, and just wants
 * to see what people are saying. That is why it is a separate route rather than
 * a signed-in variant of the landing page, and why `/` does not redirect here.
 *
 * Public on purpose. Discovery that demands an account is discovery nobody
 * does, and every review shown here is already published and public. Signing in
 * changes the ranking, not the access: `for-you` moves the reader's chosen
 * categories to the front and keeps one voice from owning the page.
 */
export default async function FeedPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string; page?: string }>;
}) {
  const { tab, page } = await searchParams;
  const recent = tab === "recent";
  const pageNum = Math.max(1, Math.min(50, Number(page) || 1));
  const offset = (pageNum - 1) * PAGE_SIZE;

  const token = await getSessionToken();
  const [me, cards] = await Promise.all([
    getUser().catch(() => null),
    getFeed({
      // "Recent" is plainly chronological. "For You" ranks, and only does
      // anything for a reader the API can identify.
      mode: recent ? "plain" : "for-you",
      sort: recent ? "newest" : "wilson",
      limit: PAGE_SIZE,
      offset,
      token,
    }),
  ]);

  const headerUser: HeaderUser = me ? { username: me.username, avatarUrl: me.avatar_url, role: me.role } : null;
  // The reader's chosen slugs, resolved to their proper labels. An interest the
  // vocabulary no longer knows is dropped rather than rendered as a raw slug.
  const chosen = (me?.interests ?? []) as string[];
  const railCategories =
    chosen.length > 0 ? INTERESTS.filter((i) => chosen.includes(i.slug)) : INTERESTS.slice(0, 8);
  const hasMore = (cards?.length ?? 0) === PAGE_SIZE;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={headerUser} />

      <main className="flex-1">
        <BrowseLayout
          current="feed"
          aside={
            <>
              <h2 className={RAIL_LABEL}>
                {chosen.length > 0 ? "Your interests" : "Browse by category"}
              </h2>
              <ul className="mt-3 flex flex-wrap gap-2">
                {railCategories.map((category) => (
                  <li key={category.slug}>
                    <Link
                      href={`/search?category=${encodeURIComponent(category.slug)}`}
                      className="inline-block rounded-[var(--radius-pill)] px-3 py-1.5 text-[13px] text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)] hover:text-[var(--accent-primary)]"
                    >
                      {category.label}
                    </Link>
                  </li>
                ))}
              </ul>

              {chosen.length === 0 && me ? (
                <p className="mt-4 text-[13px] text-[var(--text-secondary)]">
                  <Link
                    href="/onboarding"
                    className="font-semibold text-[var(--accent-primary)] hover:underline"
                  >
                    Pick your interests
                  </Link>{" "}
                  and this feed starts with them.
                </p>
              ) : null}
              <TakePartGroup className="mt-8" />
            </>
          }
        >
          <h1 className="text-[24px] font-bold text-[var(--text-primary)] lg:text-[30px]">
            {recent ? "Recent reviews" : "For you"}
          </h1>
          <p className="mt-1 max-w-[46ch] text-[14px] text-[var(--text-secondary)]">
            {recent
              ? "Everything the community has published lately, newest first."
              : me
                ? "Ranked by how helpful people found it, weighted towards what you said you care about."
                : "Ranked by how helpful people found it. Sign in and we'll weight it towards your interests."}
          </p>

          <div
            role="tablist"
            aria-label="Feed"
            className="mt-5 flex gap-1 border-b border-[var(--border-subtle)]"
          >
            <Tab href="/feed" label="For you" active={!recent} />
            <Tab href="/feed?tab=recent" label="Recent" active={recent} />
          </div>

          {cards === null ? (
            <Empty
              title="We couldn't load the feed"
              body="That's on us, not you. Try again in a moment."
            />
          ) : cards.length === 0 ? (
            <Empty
              title={pageNum > 1 ? "That's the end of the feed" : "Nothing here yet"}
              body={
                pageNum > 1
                  ? "You've reached the last page."
                  : "No published reviews match this view yet."
              }
            />
          ) : (
            <>
              <div className="mt-1">
                {cards.map((card, i, all) => (
                  <FeedCard
                    key={card.id}
                    review={card}
                    imageHints={listImageHints(i, firstImageIndex(all, (x) => Boolean(x.imageUrl)), 4)}
                  />
                ))}
              </div>

              {/* Page links rather than infinite scroll: a feed you cannot
                      get back to the bottom of is a feed you cannot share. */}
              {pageNum > 1 || hasMore ? (
                <nav aria-label="Feed pages" className="mt-6 flex items-center justify-between">
                  {pageNum > 1 ? (
                    <PageLink href={pageHref(recent, pageNum - 1)} label="← Newer" />
                  ) : (
                    <span />
                  )}
                  {hasMore ? (
                    <PageLink href={pageHref(recent, pageNum + 1)} label="Older →" />
                  ) : (
                    <span />
                  )}
                </nav>
              ) : null}
            </>
          )}
        </BrowseLayout>
      </main>

      <SiteFooter />
    </div>
  );
}

function pageHref(recent: boolean, page: number): string {
  const params = new URLSearchParams();
  if (recent) params.set("tab", "recent");
  if (page > 1) params.set("page", String(page));
  const qs = params.toString();
  return qs ? `/feed?${qs}` : "/feed";
}

function Tab({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      role="tab"
      aria-selected={active}
      className={[
        "-mb-px border-b-2 px-4 py-2.5 text-[14px] font-semibold transition-colors",
        active
          ? "border-[var(--accent-primary)] text-[var(--text-primary)]"
          : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
      ].join(" ")}
    >
      {label}
    </Link>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-8 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-8 text-center shadow-[var(--shadow-hairline-inset)]">
      <p className="text-[16px] font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="mt-1 text-[14px] text-[var(--text-secondary)]">{body}</p>
    </div>
  );
}

function PageLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="rounded-[var(--radius-pill)] px-4 py-2 text-[13px] font-semibold text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] hover:text-[var(--accent-primary)]"
    >
      {label}
    </Link>
  );
}
