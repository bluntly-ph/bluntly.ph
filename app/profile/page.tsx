import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Coins, PencilSimple, SealCheck, ShieldCheck, SignOut } from "@phosphor-icons/react/dist/ssr";

import { logout } from "@/app/actions/auth";
import { ProfileCommentRow } from "@/components/profile/ProfileCommentRow";
import { readProfileTab } from "@/components/profile/profile-tabs-model";
import { ProfileHeader, ProfileLayout, ProfileTabs } from "@/components/profile/ProfileHeader";
import { ProfileReviewCard } from "@/components/profile/ProfileReviewCard";
import { ProfileShareButton } from "@/components/profile/ProfileShareButton";
import { ProfileStats } from "@/components/profile/ProfileStats";
import { SiteFooter } from "@/components/site/SiteFooter";
import { Unavailable } from "@/components/site/Unavailable";
import { SiteHeader } from "@/components/site/SiteHeader";
import { Button } from "@/components/ui/Button";
import { getAuthoredComments } from "@/lib/comments";
import { requireOnboardedUser } from "@/lib/dal";
import { INTERESTS } from "@/lib/interests";
import { joinedLabel } from "@/lib/relative-time";
import { getMyReviews } from "@/lib/reviews";
import { getSessionToken } from "@/lib/session";
import { trustLevelName } from "@/lib/trust";
import { getTrustProfile } from "@/lib/trust-data";
import { firstImageIndex, listImageHints } from "@/lib/list-image-hints";

export const metadata: Metadata = {
  title: "Your profile — bluntly",
};

const interestLabel = (slug: string) => INTERESTS.find((i) => i.slug === slug)?.label ?? slug;

/** Chip/Action (7166:4933): 32px, a dark 1px outline at radius 16, a 20px glyph 4px before 12px Light. */
const CHIP =
  "inline-flex h-8 cursor-pointer items-center gap-1 rounded-[16px] border border-[var(--text-primary)] px-[11px] text-[12px] font-light leading-none text-[var(--text-primary)] no-underline hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]";

/**
 * The signed-in member's own profile: Figma "Profile Page - Reviews /
 * Comments / Stats" (5446:4328, 5446:6398, 5446:6532) — see ProfileHeader,
 * ProfileReviewCard, ProfileCommentRow and ProfileStats for the values.
 *
 * All three sections live on this one route, switched by `?tab=`: they share
 * the identity panel, which is most of the page and most of the fetching.
 *
 * INTENTIONAL PRODUCT DIFFERENCES: the figures are the account's real ones
 * (reviews published, verified reviews, Honesty Score) rather than the frame's
 * "People helped" and "Buyers guided", which are not served per member; the
 * owner's own controls — edit, earnings, log out — and the interests they
 * chose sit under the meta line, where the frame has a bio.
 *
 * The review list is fetched on every tab because the identity panel counts it;
 * the comment list and the trust profile are fetched only when their own tab is
 * open, since nothing above them reads either one.
 */
export default async function ProfilePage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const me = await requireOnboardedUser();
  const tab = readProfileTab((await searchParams).tab);
  // The author's own reviews in every state — pending ones included, marked as
  // such. The public feed left a just-submitted review out (it is held for
  // moderation), so it "disappeared" from its author's profile on refresh.
  const reviews = await getMyReviews(await getSessionToken());
  const comments = tab === "comments" ? await getAuthoredComments(me.id) : null;
  const trust = tab === "stats" ? await getTrustProfile(me.id) : null;
  const name = me.username || me.display_name || "You";

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url, role: me.role }} />
      <ProfileLayout
        header={
          <ProfileHeader
            name={name}
            avatarUrl={me.avatar_url}
            avatarHue={24}
            trustLevel={me.trust_level_name ?? trustLevelName(me.trust_stage) ?? "Member"}
            meta={[me.display_name && me.username ? me.display_name : null, joinedLabel(me.created_at)].filter(
              (m): m is string => Boolean(m),
            )}
            stats={[
              {
                value: String(reviews?.length ?? "—"),
                label: "Reviews written",
                icon: PencilSimple,
              },
              {
                value: String(me.verified_review_count),
                label: "Verified reviews",
                icon: SealCheck,
              },
              {
                value: String(Math.round(Number(me.reputation_score) || 0)),
                label: "Honesty Score",
                icon: ShieldCheck,
              },
            ]}
            share={<ProfileShareButton name={name} path={`/u/${me.id}`} />}
          >
            {me.interests?.length ? (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-[12px] font-light leading-none text-[var(--text-primary)]">Shops for:</span>
                {me.interests.map((slug) => (
                  <span
                    key={slug}
                    className="rounded-[4px] bg-[#d9d9d9] px-2 py-1 text-[10px] leading-none text-[var(--text-primary)]"
                  >
                    {interestLabel(slug)}
                  </span>
                ))}
              </div>
            ) : null}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {/* BUG-035: this was `/onboarding`, which walked a member who
                  has been here for months back through the four-step
                  introduction to change their display name. */}
              <Link href="/profile/edit" className={CHIP}>
                <PencilSimple size={20} weight="light" aria-hidden="true" /> Edit profile
              </Link>
              <Link href="/dashboard" className={CHIP}>
                <Coins size={20} weight="light" aria-hidden="true" /> Earnings
              </Link>
              <form action={logout}>
                <button type="submit" className={`${CHIP} bg-transparent`}>
                  <SignOut size={20} weight="light" aria-hidden="true" /> Log out
                </button>
              </form>
            </div>
          </ProfileHeader>
        }
      >
        <ProfileTabs active={tab} base="/profile" />

        {tab === "stats" ? <ProfileStats trust={trust} /> : null}

        {tab === "comments" ? (
          comments === null ? (
            <div className="px-4 md:px-0">
              <Unavailable what="your comments" />
            </div>
          ) : comments.length > 0 ? (
            <ul className="md:mt-6 md:grid md:grid-cols-2 md:gap-4 lg:gap-5">
              {comments.map((c) => (
                <ProfileCommentRow key={c.id} comment={c} />
              ))}
            </ul>
          ) : (
            <div className="px-4 pt-10 text-center">
              <p className="text-[16px] leading-none tracking-[0.8px] text-[var(--text-primary)]">
                No comments yet
              </p>
              <p className="mt-[9px] text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
                Join a discussion under a review and it will show up here.
              </p>
              <Button href="/search" className="mt-6 gap-1">
                Find a review
                <ArrowRight size={20} aria-hidden="true" />
              </Button>
            </div>
          )
        ) : null}

        {tab === "reviews" ? (
          reviews === null ? (
            <div className="px-4 md:px-0">
              <Unavailable what="your reviews" />
            </div>
          ) : reviews.length > 0 ? (
            <ul className="md:mt-6 md:grid md:grid-cols-2 md:gap-4 lg:gap-5">
              {/* A profile card's photo is 358px square: only the first is on screen. */}
              {reviews.map((r, i, all) => (
                <ProfileReviewCard
                  key={r.id}
                  review={r}
                  status={r.status}
                  rejectionReason={r.rejectionReason}
                  imageHints={listImageHints(i, firstImageIndex(all, (x) => Boolean(x.imageUrl)), 1)}
                />
              ))}
            </ul>
          ) : (
            <div className="px-4 pt-10 text-center">
              <p className="text-[16px] leading-none tracking-[0.8px] text-[var(--text-primary)]">
                No reviews yet
              </p>
              <p className="mt-[9px] text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
                Share an honest review and start earning from your opinions.
              </p>
              <Button href="/reviews/new" className="mt-6 gap-1">
                Write a review
                <ArrowRight size={20} aria-hidden="true" />
              </Button>
            </div>
          )
        ) : null}
      </ProfileLayout>
      <SiteFooter />
    </div>
  );
}
