import Link from "next/link";
import { ArrowsLeftRight, Compass, Megaphone, Question, UserCircle } from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";
import type { ReactNode } from "react";

/**
 * The browsing pages' desktop frame — Feed, Reviews (search), Q&A, Requests.
 *
 * The Figma pack draws these as phone screens, and a phone column centred on a
 * monitor is what the owner rejected (review, 2026-09-16). From `lg` the same
 * content gets a website's information architecture, first built on /feed and
 * shared from here so the four pages cannot drift apart:
 *
 *   lg   a navigation rail at the left, the page in the middle
 *   xl   a context rail at the right — what else this page offers, beside the
 *        content rather than buried under it
 *
 * Below `lg` none of it renders: the site header and the bottom bar already
 * carry navigation, and a rail squeezed onto a phone is a menu nobody opened.
 */
export type BrowseSection = "feed" | "reviews" | "questions" | "requests" | "profile";

const LINKS: { key: BrowseSection; href: string; icon: Icon; label: string }[] = [
  { key: "feed", href: "/feed", icon: Compass, label: "Feed" },
  { key: "reviews", href: "/search", icon: ArrowsLeftRight, label: "Reviews" },
  { key: "questions", href: "/questions", icon: Question, label: "Q&A" },
  { key: "requests", href: "/requests", icon: Megaphone, label: "Requests" },
  { key: "profile", href: "/profile", icon: UserCircle, label: "Profile" },
];

/** The heading over a rail group: 12px, uppercase, wide-tracked. */
// Secondary ink, not muted: rail labels were --text-muted (40% ink, 2.39:1 on the app surface) and failed WCAG AA contrast in Lighthouse on every desktop page (2026-09-17). These rails are desktop-only layout with no Figma frame, so the AA-passing secondary ink (70%, 5.3:1) is used, not a design value.
export const RAIL_LABEL = "text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--text-secondary)]";

/** A link in a rail group. */
export const RAIL_ACTION = "text-[var(--text-secondary)] hover:text-[var(--accent-primary)]";

/**
 * The page frame: navigation rail, content, optional context rail.
 * `aside` is drawn from `xl`, where there is width for it without squeezing
 * the content column.
 */
export function BrowseLayout({
  current,
  aside,
  /**
   * The outer padding and width. Defaulted to the feed's; a page whose phone
   * geometry comes from a Figma frame passes its own, so the rails change the
   * website without touching the frame.
   */
  outerClassName = "mx-auto w-full max-w-[76rem] px-4 py-6 sm:px-6 lg:px-10 lg:py-10",
  contentClassName = "",
  children,
}: {
  current: BrowseSection;
  aside?: ReactNode;
  outerClassName?: string;
  contentClassName?: string;
  children: ReactNode;
}) {
  return (
    <div className={outerClassName}>
      <div
        className={`lg:grid lg:grid-cols-[11rem_minmax(0,1fr)] lg:items-start lg:gap-10 ${
          aside ? "xl:grid-cols-[11rem_minmax(0,1fr)_17rem]" : ""
        }`}
      >
        <BrowseNav current={current} />
        <div className={`min-w-0 ${contentClassName}`}>{children}</div>
        {aside ? <aside className="hidden xl:block xl:sticky xl:top-28">{aside}</aside> : null}
      </div>
    </div>
  );
}

export function BrowseNav({ current }: { current: BrowseSection }) {
  return (
    <nav aria-label="Browse" className="hidden lg:sticky lg:top-28 lg:block">
      <ul className="flex flex-col gap-0.5">
        {LINKS.map(({ key, href, icon: Glyph, label }) => {
          const isCurrent = key === current;
          return (
            <li key={key}>
              <Link
                href={href}
                aria-current={isCurrent ? "page" : undefined}
                className={`flex items-center gap-2.5 rounded-[var(--radius-md)] px-3 py-2 text-[14px] ${
                  isCurrent
                    ? "font-semibold text-[var(--accent-primary)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] hover:text-[var(--text-primary)]"
                }`}
              >
                <Glyph size={18} weight={isCurrent ? "fill" : "regular"} />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** One group in the context rail: a label over its links. */
export function RailGroup({
  title,
  className = "",
  children,
}: {
  title: string;
  className?: string;
  children: ReactNode;
}) {
  // Every link in a rail list is at least 24px tall (WCAG 2.5.8, and
  // e2e/accessibility.spec.ts): 13px text on its natural line made 19px
  // targets, which failed that check on /search and /questions.
  return (
    <section
      className={`[&_li>a]:inline-flex [&_li>a]:min-h-6 [&_li>a]:items-center ${className ?? ""}`}
    >
      <h2 className={RAIL_LABEL}>{title}</h2>
      {children}
    </section>
  );
}

/** The four things a reader can start from any browsing page. */
export function TakePartGroup({ className = "" }: { className?: string }) {
  return (
    <RailGroup title="Take part" className={className}>
      <ul className="mt-3 flex flex-col gap-2 text-[13px]">
        <li>
          <Link href="/reviews/new" className={RAIL_ACTION}>
            Write a review
          </Link>
        </li>
        <li>
          <Link href="/questions/new" className={RAIL_ACTION}>
            Ask a question
          </Link>
        </li>
        <li>
          <Link href="/requests" className={RAIL_ACTION}>
            Request a review
          </Link>
        </li>
        <li>
          <Link href="/compare" className={RAIL_ACTION}>
            Compare products
          </Link>
        </li>
      </ul>
    </RailGroup>
  );
}
