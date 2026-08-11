import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { PencilSimpleLine, SealCheck, ShieldCheck, Star } from "@phosphor-icons/react/dist/ssr";

import { logout } from "@/app/actions/auth";
import { ReviewCard } from "@/components/review/ReviewCard";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { Button } from "@/components/ui/Button";
import { requireOnboardedUser } from "@/lib/dal";
import { INTERESTS } from "@/lib/interests";
import { searchReviews } from "@/lib/reviews";

export const metadata: Metadata = {
  title: "Your profile — bluntly",
};

const interestLabel = (slug: string) =>
  INTERESTS.find((i) => i.slug === slug)?.label ?? slug;

export default async function ProfilePage() {
  const me = await requireOnboardedUser();
  const reviews = await searchReviews({
    author_id: me.id,
    sort: "newest",
    limit: 24,
  });
  const name = me.display_name || me.username || "You";

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="mx-auto w-full max-w-[72rem] flex-1 px-6 py-8 lg:px-10 lg:py-10">
        {/* Profile header */}
        <section className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <span className="relative grid h-20 w-20 shrink-0 place-items-center overflow-hidden rounded-full text-[26px] font-bold text-white ring-1 ring-[var(--line-hairline-10)]" style={{ background: "hsl(24 55% 55%)" }}>
            {me.avatar_url ? (
              <Image src={me.avatar_url} alt="" fill sizes="80px" className="object-cover" />
            ) : (
              name.slice(0, 1).toUpperCase()
            )}
          </span>
          <div className="flex-1">
            <h1 className="text-[24px] font-bold text-[var(--text-primary)]">{name}</h1>
            {me.username ? (
              <p className="text-[14px] text-[var(--text-secondary)]">@{me.username}</p>
            ) : null}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] bg-[color-mix(in_srgb,var(--accent-trust)_12%,transparent)] px-3 py-1 text-[12px] font-medium text-[var(--accent-trust)]">
                <ShieldCheck size={14} weight="fill" />
                {me.trust_level_name ?? `Stage ${me.trust_stage}`}
              </span>
              <span className="rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-3 py-1 text-[12px] capitalize text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]">
                {me.membership_tier} member
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <Link href="/dashboard" className="contents">
              <Button size="sm">Earnings</Button>
            </Link>
            <Link href="/onboarding" className="contents">
              <Button variant="secondary" size="sm" icon={<PencilSimpleLine size={14} />}>
                Edit
              </Button>
            </Link>
            <form action={logout}>
              <Button type="submit" variant="secondary" size="sm">
                Log out
              </Button>
            </form>
          </div>
        </section>

        {/* Stats */}
        <section className="mt-6 grid grid-cols-3 gap-3 sm:max-w-[28rem]">
          <Stat icon={<SealCheck size={18} weight="fill" className="text-[var(--accent-success)]" />} value={me.verified_review_count} label="Verified" />
          <Stat icon={<Star size={18} weight="fill" className="text-[var(--accent-star)]" />} value={me.reputation_score} label="Reputation" />
          <Stat value={reviews.length} label="Published" />
        </section>

        {/* Interests */}
        {me.interests?.length ? (
          <section className="mt-6">
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
              Shops for
            </h2>
            <ul className="mt-2 flex flex-wrap gap-2">
              {me.interests.map((slug) => (
                <li key={slug} className="rounded-[var(--radius-md)] bg-[var(--surface-card)] px-3 py-1 text-[13px] text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]">
                  {interestLabel(slug)}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {/* Reviews */}
        <section className="mt-10">
          <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Your reviews</h2>
          {reviews.length > 0 ? (
            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 md:gap-6 lg:grid-cols-4">
              {reviews.map((r) => (
                <ReviewCard key={r.id} review={r} />
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-8 text-center shadow-[var(--shadow-hairline-inset)]">
              <p className="text-[15px] font-semibold text-[var(--text-primary)]">
                No published reviews yet
              </p>
              <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
                Share an honest review and start earning from your opinions.
              </p>
              <Link href="/reviews/new" className="mt-4 inline-block">
                <Button size="sm">Write a review</Button>
              </Link>
            </div>
          )}
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

function Stat({
  icon,
  value,
  label,
}: {
  icon?: React.ReactNode;
  value: React.ReactNode;
  label: string;
}) {
  return (
    <div className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 text-center shadow-[var(--shadow-hairline-inset)]">
      <div className="flex items-center justify-center gap-1 text-[20px] font-bold text-[var(--text-primary)]">
        {icon}
        {value}
      </div>
      <div className="mt-1 text-[12px] text-[var(--text-muted)]">{label}</div>
    </div>
  );
}
