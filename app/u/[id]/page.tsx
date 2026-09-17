import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PencilSimple, SealCheck, ShieldCheck } from "@phosphor-icons/react/dist/ssr";

import { ProfileHeader, ProfileLayout, ProfileTabs } from "@/components/profile/ProfileHeader";
import { ProfileReviewCard } from "@/components/profile/ProfileReviewCard";
import { ProfileShareButton } from "@/components/profile/ProfileShareButton";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getUser } from "@/lib/dal";
import { joinedLabel } from "@/lib/relative-time";
import { firstImageIndex, listImageHints } from "@/lib/list-image-hints";
import { getAuthorProfile } from "@/lib/reviews";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const data = await getAuthorProfile(id);
  const name = data?.author.name ?? "Reviewer";
  return {
    title: `${name} — bluntly`,
    description: data ? `Honest reviews by ${name} on bluntly.` : undefined,
  };
}

/** Stable 0–359 hue from a string, for the placeholder avatar tint. */
function hue(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) h = (h * 31 + seed.charCodeAt(i)) % 360;
  return h;
}

/**
 * A reviewer's public profile, built to Figma "Profile Page - Reviews"
 * (5446:4328) — see ProfileHeader and ProfileReviewCard.
 *
 * THE SEGMENT IS A HANDLE OR AN ID (BUG-030). The folder is still `[id]`
 * because that is what the site links, but `/u/ciel` is what a person types,
 * and it used to 404 for every reviewer alive: the page resolved its subject
 * through the review feed's `author_id`, which takes a UUID. It now resolves
 * through `GET /users/public/{handle}`, which takes either.
 *
 * A REVIEWER WITH NOTHING PUBLISHED IS NOT A 404. That was the same bug's
 * second half — no feed row meant "not found" for an account that plainly
 * exists. They get their profile and an honest empty state. `notFound()` is
 * now reserved for a handle that belongs to nobody.
 *
 * INTENTIONAL PRODUCT DIFFERENCES: followers and a bio are not stored, so the
 * meta line carries the display name and the join date; "People helped" and
 * "Buyers guided" are not served per member, so the figures are the ones this
 * reviewer actually has. The Comments and Stats tabs are the member's own
 * (`/profile`) — a stranger gets Reviews, which is the public surface.
 */
export default async function ReviewerProfilePage({ params }: Params) {
  const { id } = await params;
  const [data, me] = await Promise.all([getAuthorProfile(id), getUser().catch(() => null)]);

  // `notFound()` rather than rendering the message inline, which returned 200.
  // `/u/{id}` accepts any id, so a soft 404 here meant every made-up id was a
  // real, indexable page; Next injects `<meta name="robots" content="noindex">`
  // only for responses that actually 404. The wording lives in
  // `not-found.tsx` beside this file.
  if (!data) notFound();

  const { author, cards } = data;
  // The handle, when there is one: a profile URL someone pastes should read
  // `/u/ciel`, not a UUID. Falls back to the id for an account without one.
  const publicPath = `/u/${author.username ?? author.id}`;
  const user: HeaderUser = me ? { username: me.username, avatarUrl: me.avatar_url, role: me.role } : null;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <ProfileLayout
        header={
          <ProfileHeader
            name={author.username ?? author.name}
            avatarUrl={author.avatarUrl}
            avatarHue={hue(author.name)}
            trustLevel={author.trust}
            meta={[
              author.username && author.name !== author.username ? author.name : null,
              joinedLabel(author.joinedAt),
            ].filter((m): m is string => Boolean(m))}
            stats={[
              {
                value: String(cards.length),
                label: "Reviews written",
                icon: PencilSimple,
              },
              {
                value: String(author.verifiedReviewCount),
                label: "Verified reviews",
                icon: SealCheck,
              },
              ...(author.trustScore
                ? [
                    {
                      value: String(Math.round(Number(author.trustScore) || 0)),
                      label: "Honesty Score",
                      icon: ShieldCheck,
                    },
                  ]
                : []),
            ]}
            share={<ProfileShareButton name={author.name} path={publicPath} />}
          />
        }
      >
        <ProfileTabs />

        {cards.length > 0 ? (
          <ul className="md:mt-6 md:grid md:grid-cols-2 md:gap-4 lg:gap-5">
            {/* A profile card's photo is 358px square: only the first is on screen. */}
            {cards.map((r, i, all) => (
              <ProfileReviewCard
                key={r.id}
                review={r}
                imageHints={listImageHints(i, firstImageIndex(all, (x) => Boolean(x.imageUrl)), 1)}
              />
            ))}
          </ul>
        ) : (
          /* A real reviewer who has not published yet. Saying so is the point
             of BUG-030's fix — this page used to 404 instead. */
          <div className="px-4 pt-10 text-center">
            <p className="text-[16px] leading-none tracking-[0.8px] text-[var(--text-primary)]">
              No published reviews yet
            </p>
            <p className="mt-[9px] text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
              When {author.name} publishes a review, it will appear here.
            </p>
          </div>
        )}
      </ProfileLayout>
      <SiteFooter />
    </div>
  );
}
