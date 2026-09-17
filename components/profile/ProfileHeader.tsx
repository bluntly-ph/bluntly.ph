import Image from "next/image";
import Link from "next/link";

import {
  PROFILE_TABS,
  PROFILE_TAB_LABEL,
  profileTabHref,
  type ProfileTab,
} from "@/components/profile/profile-tabs-model";
import { DotOutline } from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";

export type ProfileStat = { value: string; label: string; icon: Icon };

const Dot = () => <DotOutline size={12} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />;

/**
 * The top of a reviewer's profile: Figma "Profile Page - Reviews" (5446:4328),
 * read 2026-09-15, less its status bar and nav.
 *
 *   cover   a 116px band edge to edge
 *   panel   white, from the cover down: the 80px avatar overlapping the cover
 *           by 34px, 32px in; a share control against the right, 13px down;
 *           the name 62px into the panel in 20px SemiBold with the trust pill
 *           12px after it (the bluntly mark and 10px Regular brand orange on
 *           the tint at radius 8); the meta line 4px under it in 12px Regular
 *           at 70% split by DotOutline; then the figures 46px lower — values in
 *           16px SemiBold brand orange with a 20px glyph, labels 12px under
 *           them in 12px Regular, 28px apart and centred; 38px of panel below
 *
 * INTENTIONAL PRODUCT DIFFERENCES: no member uploads a cover, so the band is
 * the brand gradient; followers and a bio are not served, so the meta line
 * carries the handle and the join date; the figures are the ones the account
 * actually has (see the pages).
 */
export function ProfileHeader({
  name,
  avatarUrl,
  avatarHue,
  trustLevel,
  meta,
  stats,
  share,
  children,
}: {
  name: string;
  avatarUrl: string | null;
  /** Tint for the initial when there is no photo. */
  avatarHue: number;
  trustLevel: string;
  meta: string[];
  stats: ProfileStat[];
  share?: React.ReactNode;
  /** Account-specific rows under the meta line (interests, actions). */
  children?: React.ReactNode;
}) {
  return (
    <section>
      <div aria-hidden="true" className="h-[116px] bg-[image:var(--brand-gradient)] md:rounded-t-[16px]" />
      <div className="relative bg-[var(--surface-card)] px-8 pb-[38px] md:rounded-b-[16px] md:shadow-[var(--shadow-card)]">
        <span
          className="absolute -top-[34px] left-8 grid h-20 w-20 place-items-center overflow-hidden rounded-full text-[28px] font-semibold text-white"
          style={avatarUrl ? undefined : { background: `hsl(${avatarHue} 55% 55%)` }}
        >
          {avatarUrl ? (
            <Image src={avatarUrl} alt="" fill sizes="80px" className="object-cover" />
          ) : (
            <span aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
          )}
        </span>
        {share ? <div className="absolute right-6 top-[5px]">{share}</div> : null}

        <div className="pt-[62px]">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[20px] font-semibold leading-none text-[var(--text-primary)]">{name}</h1>
            <span className="inline-flex items-center gap-1 rounded-[8px] bg-[rgba(239,88,33,0.1)] px-2 py-1 text-[10px] leading-none text-[var(--accent-primary)]">
              <Image src="/icon.svg" alt="" width={12} height={12} unoptimized className="h-3 w-3" />
              {trustLevel}
            </span>
          </div>
          {meta.length > 0 ? (
            <p className="mt-1 flex flex-wrap items-center gap-1 text-[12px] leading-[18px] text-[rgba(32,32,32,0.7)]">
              {meta.map((m, i) => (
                <span key={m} className="inline-flex items-center gap-1">
                  {i > 0 ? <Dot /> : null}
                  {m}
                </span>
              ))}
            </p>
          ) : null}
          {children}
        </div>

        {/* One row, as drawn: equal columns that stay put at every phone width
            and let a longer label wrap inside its own column rather than push a
            figure onto a second row. The 28px gap is the frame's; the columns
            reach into the panel's 32px gutter so three labels fit at 390. */}
        <dl
          className="-mx-4 mt-[46px] grid gap-x-3"
          style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}
        >
          {stats.map(({ value, label, icon: Glyph }) => (
            <div key={label} className="flex flex-col-reverse items-center gap-3 text-center">
              <dt className="text-[12px] leading-none text-[var(--text-primary)]">{label}</dt>
              <dd className="flex items-center gap-1 text-[16px] font-semibold leading-none text-[var(--accent-primary)]">
                {value}
                <Glyph size={20} aria-hidden="true" />
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

/**
 * The profile page's frame. Phone: one column, as the frame draws it. From
 * `lg` the identity card stands on its own at the left and stays in view
 * while the reviews scroll beside it, so a monitor is not one 42rem strip of
 * square photos down the middle (owner review, 2026-09-16).
 */
export function ProfileLayout({ header, children }: { header: React.ReactNode; children: React.ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-[42rem] flex-1 pb-16 md:px-6 md:pt-6 lg:grid lg:max-w-[72rem] lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-start lg:gap-10 lg:px-10 lg:pt-10">
      <div className="lg:sticky lg:top-[96px]">{header}</div>
      <div className="min-w-0">{children}</div>
    </main>
  );
}

export type { ProfileTab };

/**
 * The profile's section tabs, 16px under the panel: 14px Regular 60px apart,
 * the current one in ink and the rest in #8c8c8c, over a full-bleed hairline
 * 23px lower. Figma "Profile Page - Reviews / Comments / Stats"
 * (5446:4328 / 5446:6398 / 5446:6532).
 *
 * The three sections are one route, switched by `?tab=`, because they share the
 * whole identity panel above them — a separate route per tab would rebuild and
 * re-fetch that panel to change a list. `base` is the route the links point at,
 * so the same component serves your own profile and someone else's.
 *
 * A tab with no `base` is not linked at all: the public profile has no comment
 * or stats list behind it yet, and a tab that navigates nowhere is worse than
 * one that is absent.
 */
export function ProfileTabs({
  active = "reviews",
  base,
}: {
  active?: ProfileTab;
  base?: string;
}) {
  const tabs: ProfileTab[] = base ? PROFILE_TABS : ["reviews"];

  return (
    <nav aria-label="Profile sections" className="border-b border-[var(--line-hairline-10)]">
      <ul className="flex justify-center gap-[60px] pb-[23px] pt-4 text-[14px] leading-none lg:justify-start lg:gap-10 lg:pt-1">
        {tabs.map((tab) => (
          <li
            key={tab}
            // The current tab's 1px trust-blue rule, sitting on the section
            // hairline and running ~14px past the label each side: Figma Group
            // 917 draws it 83px wide at x36 over the full-bleed line (5446:4328).
            // It was missing, which left the current tab marked by ink colour
            // alone (compared against the frame 2026-09-17).
            className={
              tab === active
                ? "relative after:absolute after:-bottom-[24px] after:-left-[14px] after:-right-[14px] after:h-px after:bg-[var(--accent-trust)]"
                : undefined
            }
          >
            {tab === active ? (
              <span aria-current="page" className="text-[var(--text-primary)]">
                {PROFILE_TAB_LABEL[tab]}
              </span>
            ) : (
              <Link
                href={profileTabHref(base ?? "", tab)}
                className="text-[var(--base-gray-400)] no-underline hover:text-[var(--text-primary)]"
              >
                {PROFILE_TAB_LABEL[tab]}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default ProfileHeader;
