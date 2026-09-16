import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PencilSimple, ShieldCheck } from "@phosphor-icons/react/dist/ssr";

import { ProfileHeader, ProfileLayout, ProfileTabs } from "@/components/profile/ProfileHeader";
import { ProfileReviewCard } from "@/components/profile/ProfileReviewCard";
import { ProfileShareButton } from "@/components/profile/ProfileShareButton";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getUser } from "@/lib/dal";
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
 * INTENTIONAL PRODUCT DIFFERENCES: the public feed carries a reviewer's
 * identity, trust and published reviews, so the figures are "Reviews written"
 * and the Honesty Score; followers, a join date, a bio, "People helped",
 * "Buyers guided" and the Comments and Stats tabs have nothing public behind
 * them and are not drawn.
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
            meta={author.username && author.name !== author.username ? [author.name] : []}
            stats={[
              {
                value: String(cards.length),
                label: "Reviews written",
                icon: PencilSimple,
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
            share={<ProfileShareButton name={author.name} path={`/u/${author.id}`} />}
          />
        }
      >
        <ProfileTabs />

        <ul className="md:mt-6 md:grid md:grid-cols-2 md:gap-4 lg:gap-5">
          {cards.map((r, i) => (
            <ProfileReviewCard key={r.id} review={r} priority={i === 0} />
          ))}
        </ul>
      </ProfileLayout>
      <SiteFooter />
    </div>
  );
}
