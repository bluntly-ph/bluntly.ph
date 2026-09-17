"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  Basket,
  CaretLeft,
  ChartLineUp,
  CodesandboxLogo,
  FingerprintSimple,
  Gear,
  IdentificationCard,
  Link as LinkIcon,
  List,
  ListChecks,
  PiggyBank,
  Question,
  Storefront,
  Tag,
  Users,
  X,
} from "@phosphor-icons/react/dist/ssr";

import { Logo } from "@/components/ui/Logo";

/**
 * The console's navigation, built to the sidebar component (5017:2225).
 *
 * Re-read from Figma on 2026-09-16 and still there, which makes it one of only
 * two surviving admin frames — see AdminShell for what happened to the rest.
 * Its four groups, in its order: MAIN (Overview, Review Queue, Q&A), MANAGE
 * (Products, Sellers, Reviewers), FINANCE (Affiliate Links, Honesty Fund),
 * SYSTEM (Activity Log, Settings), over a white 196x64 user card at radius 12.
 *
 * That component has two states — a collapsed icon rail and an expanded rail
 * with labels — so the toggle is part of the design, not an addition.
 *
 * Every item routes somewhere real. One is deliberately inert and says why on
 * its face rather than being silently clickable:
 *
 *   Settings   No console settings have been specified. Inventing some would
 *              be scope, not implementation.
 *
 * Sellers was inert too while FR-4 stood descoped (2026-07-28, reaffirmed
 * 2026-08-07; schema dropped in 0024). The completion contract reinstated it
 * (0042, 0043), so it now opens the seller-claim queue.
 *
 * `Review Queue`, `Q&A` and reports are one screen with tabs, because the
 * review-queue frame draws them that way: Review / Answer / Report / Support.
 * That was 5017:3758, which has been deleted; 6922:837 draws the same four.
 *
 * DOCUMENTED DEVIATIONS — three items the sidebar component does not draw, each
 * because a real screen exists behind it: Prices, Users and Analytics. The
 * frame keeps traffic geography on the Overview alone, and the owner asked for
 * the expanded view to be reachable from the rail rather than only from a link
 * inside a panel. Nothing in the rail routes nowhere.
 */

export type NavItem = {
  label: string;
  Icon: typeof CodesandboxLogo;
  href?: string;
  /** Matches when the path starts with this, for nested routes. */
  match?: string;
  /** Short status shown in place of a destination when the item is inert. */
  blocked?: string;
  /** The full reason, for the tooltip and for screen readers. */
  why?: string;
};

export const NAV: { heading: string; items: NavItem[] }[] = [
  {
    heading: "Main",
    items: [
      { label: "Overview", Icon: CodesandboxLogo, href: "/moderate", match: "/moderate$" },
      {
        label: "Review Queue",
        Icon: ListChecks,
        href: "/moderate/review-queue",
        match: "/moderate/review-queue",
      },
      {
        label: "Q&A",
        Icon: Question,
        href: "/moderate/review-queue?tab=answers",
        match: "tab=answers",
      },
    ],
  },
  {
    heading: "Manage",
    items: [
      { label: "Products", Icon: Basket, href: "/moderate/products", match: "/moderate/products" },
      // Not in the sidebar component (5017:2225). Community prices are pending
      // until a moderator decides them (FR-2, completion contract), and the
      // decision needs a screen.
      { label: "Prices", Icon: Tag, href: "/moderate/prices", match: "/moderate/prices" },
      {
        label: "Sellers",
        Icon: Storefront,
        href: "/moderate/sellers",
        match: "/moderate/sellers",
      },
      {
        label: "Users",
        Icon: IdentificationCard,
        href: "/moderate/users",
        match: "/moderate/users",
      },
      {
        label: "Reviewers",
        Icon: Users,
        href: "/moderate/reviewers",
        match: "/moderate/reviewers",
      },
    ],
  },
  {
    heading: "Finance",
    items: [
      {
        label: "Affiliate Links",
        Icon: LinkIcon,
        href: "/moderate/affiliate-links",
        match: "/moderate/affiliate-links",
      },
      {
        label: "Honesty Fund",
        Icon: PiggyBank,
        href: "/moderate/honesty-fund",
        match: "/moderate/honesty-fund",
      },
    ],
  },
  {
    heading: "System",
    items: [
      {
        // Not in the sidebar component (5017:2225): the frame keeps traffic on
        // the Overview only. Added on the owner's explicit instruction that the
        // geography view be reachable from the rail — "a moderator should not
        // need to guess where geography analytics live." The Overview keeps its
        // compact summary; this is the expanded view.
        label: "Analytics",
        Icon: ChartLineUp,
        href: "/moderate/analytics",
        match: "/moderate/analytics",
      },
      {
        label: "Activity Log",
        Icon: FingerprintSimple,
        href: "/moderate/activity",
        match: "/moderate/activity",
      },
      {
        label: "Settings",
        Icon: Gear,
        blocked: "Not configured",
        why: "No console settings have been specified for this build.",
      },
    ],
  },
];

/** The header title for a path, from the same table the nav renders. */
export function titleForPath(pathname: string, tab?: string | null): string {
  if (pathname === "/moderate") return "Overview";
  if (pathname.startsWith("/moderate/review-queue")) {
    if (tab === "answers") return "Q&A";
    if (tab === "report") return "Reports";
    if (tab === "support") return "Support";
    return "Review Queue";
  }
  for (const group of NAV) {
    for (const item of group.items) {
      if (item.href && pathname.startsWith(item.href.split("?")[0]) && item.href !== "/moderate") {
        return item.label;
      }
    }
  }
  return "Overview";
}

function isActive(item: NavItem, pathname: string, tab: string | null): boolean {
  if (!item.match) return false;
  if (item.match === "tab=answers") {
    return pathname.startsWith("/moderate/review-queue") && tab === "answers";
  }
  if (item.match === "/moderate$") return pathname === "/moderate";
  if (item.match === "/moderate/review-queue") {
    return pathname.startsWith("/moderate/review-queue") && tab !== "answers";
  }
  return pathname.startsWith(item.match);
}

export function AdminNav({
  moderator,
}: {
  moderator: { name: string; role: string };
}) {
  const pathname = usePathname() ?? "/moderate";
  const tab = useSearchParams()?.get("tab") ?? null;
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const width = collapsed ? "w-[64px]" : "w-[220px]";

  const rail = (
    <>
      {/* Admin/Sidebar 5017:2225, expanded state, read 2026-09-17: "Admin" in
          12px Regular trust blue 2px in, the 78x24 wordmark 18px under its top,
          both 32px from the rail's edges; the groups start 32px below (y106).
          It was an 11px SemiBold letter-spaced "ADMIN" over the word "bluntly"
          typeset in 22px Bold, which is not the wordmark. */}
      <div
        className={
          collapsed
            ? "flex justify-center pb-6 pt-8"
            : "px-8 pb-8 pt-8 [@media(max-height:900px)]:pb-4 [@media(max-height:900px)]:pt-6"
        }
      >
        {collapsed ? (
          // The collapsed state draws the 24px brand mark, not a letter.
          <Image src="/icon.svg" alt="bluntly" width={24} height={24} className="h-6 w-6" />
        ) : (
          <span className="block">
            <span className="ml-0.5 block text-[12px] leading-none text-[var(--accent-trust)]">Admin</span>
            <Logo height={24} label="bluntly" className="mt-1.5 block text-[var(--accent-primary)]" />
          </span>
        )}
      </div>

      {/* The rail scrolls on its own only if the viewport is too short for the
          items. It never moves because the workspace scrolled. */}
      {/* The groups (5017:2234): 32px apart, each a 12px Light label at 70% ink
          12px over its items; items 16px apart, a 28px glyph 8px before a 16px
          Medium label; the current item orange, glyph and word, with no pill
          behind it. They were 10px SemiBold letter-spaced labels over 14px
          items with 20px glyphs, and the current item sat on a grey pill. The
          rows keep a 4px vertical pad (inside the 16px rhythm) as a hit and
          focus area.

          SHORT SCREENS. The frame's rail holds eight items; this one holds
          thirteen (see NAV). At the frame's own 832px height the source rhythm
          pushed the whole SYSTEM group below the rail's fold, so from 801 to
          900px tall the same type and glyphs sit on a 36px pitch instead of 44,
          and at 800px and under on 28px — the glyph's own height, still above
          the 24px minimum target. The two ranges do not overlap, so neither
          depends on the order Tailwind emits them in. */}
      <nav aria-label="Admin sections" className={`min-h-0 flex-1 overflow-y-auto ${collapsed ? "px-2" : "px-6"}`}>
        {NAV.map((group) => (
          <div key={group.heading} className="mb-8 last:mb-4 [@media(min-height:801px)_and_(max-height:900px)]:mb-4 [@media(max-height:800px)]:mb-3 [@media(max-height:800px)]:last:mb-2">
            {!collapsed ? (
              <p className="px-2 pb-2 text-[12px] font-light uppercase leading-none text-[var(--text-secondary)] [@media(min-height:801px)_and_(max-height:900px)]:pb-1.5 [@media(max-height:800px)]:pb-1">
                {group.heading}
              </p>
            ) : (
              <hr className="mx-3 mb-2 border-[var(--border-subtle)]" />
            )}
            <ul className="flex flex-col gap-2 [@media(min-height:801px)_and_(max-height:900px)]:gap-1 [@media(max-height:800px)]:gap-0">
              {group.items.map((item) => {
                const { label, Icon, href, blocked, why } = item;
                const active = isActive(item, pathname, tab);
                const base = `flex items-center gap-2 rounded-[var(--radius-sm)] px-2 py-1 text-[16px] font-medium leading-none [@media(min-height:801px)_and_(max-height:900px)]:py-0.5 [@media(max-height:800px)]:py-0 ${
                  collapsed ? "justify-center px-0" : ""
                }`;
                return (
                  <li key={label}>
                    {href ? (
                      <Link
                        href={href}
                        onClick={() => setDrawerOpen(false)}
                        aria-current={active ? "page" : undefined}
                        title={collapsed ? label : undefined}
                        className={`${base} transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
                          active
                            ? "text-[var(--accent-primary)]"
                            : "text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
                        }`}
                      >
                        <Icon size={28} weight="regular" className="shrink-0" />
                        {!collapsed ? <span className="truncate">{label}</span> : null}
                      </Link>
                    ) : (
                      /* Not a link and not a button: nothing to click, nothing
                         to focus, no destination to 404. The status is on its
                         face and the full reason is available to a pointer and
                         to a screen reader. */
                      <span
                        title={why}
                        aria-disabled="true"
                        className={`${base} cursor-not-allowed text-[var(--text-muted)]`}
                      >
                        <Icon size={28} weight="regular" className="shrink-0" />
                        {!collapsed ? (
                          <span className="flex min-w-0 flex-1 flex-col">
                            <span className="truncate">{label}</span>
                            <span className="truncate text-[10px] font-normal leading-tight text-[var(--text-muted)]">
                              {blocked}
                            </span>
                          </span>
                        ) : null}
                        <span className="sr-only">{`Unavailable. ${why ?? ""}`}</span>
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* The user card (5017:2334): 196x64 at radius 12, 12px in; a 40px
          avatar 16px in and 12px down; the name in 14px Medium over the role
          in 12px Light at 70%, 16px apart top to top. The frame's card is white
          on a #f2f2f2 rail; this rail is white, as 6922:837 draws the rail on
          the page, so the card keeps a hairline to read as a card. */}
      <div
        className={`m-3 flex h-16 items-center gap-3 rounded-[12px] px-4 shadow-[var(--shadow-hairline-inset)] ${
          collapsed ? "justify-center px-0" : ""
        }`}
      >
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--accent-primary)] text-[14px] font-bold text-[var(--text-on-brand)]">
          {moderator.name.slice(0, 1).toUpperCase()}
        </span>
        {!collapsed ? (
          <span className="min-w-0">
            <span className="block truncate text-[14px] font-medium leading-none text-[var(--text-primary)]">
              {moderator.name}
            </span>
            <span className="mt-0.5 block text-[12px] font-light capitalize leading-none text-[var(--text-secondary)]">
              {moderator.role}
            </span>
          </span>
        ) : null}
      </div>

      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
        className="mx-2 mb-2 hidden items-center justify-center gap-2 rounded-[var(--radius-sm)] px-3 py-2 text-[12px] font-medium text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] lg:flex"
      >
        <CaretLeft size={16} className={collapsed ? "rotate-180" : ""} />
        {!collapsed ? "Collapse" : null}
      </button>
    </>
  );

  return (
    <>
      {/* Desktop rail: full height, never scrolls with the workspace. */}
      <aside
        className={`hidden h-full ${width} shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--surface-card)] transition-[width] lg:flex`}
      >
        {rail}
      </aside>

      {/* Below lg the rail becomes a drawer, per the frame's responsive intent. */}
      <button
        type="button"
        onClick={() => setDrawerOpen(true)}
        aria-label="Open admin navigation"
        /* Was bottom-[84px] to clear the site's mobile tab bar, which sat at
           the same z-index. That bar was removed on 2026-09-12, so the offset
           now just floats the button 84px off the bottom for no reason. */
        className="fixed bottom-4 left-4 z-50 grid h-11 w-11 place-items-center rounded-full bg-[var(--accent-primary)] text-[var(--text-on-brand)] shadow-[var(--shadow-fab)] lg:hidden"
      >
        <List size={22} weight="bold" />
      </button>

      {drawerOpen ? (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setDrawerOpen(false)}
            aria-hidden
          />
          <aside className="relative flex h-full w-[248px] flex-col border-r border-[var(--border-subtle)] bg-[var(--surface-card)]">
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              aria-label="Close admin navigation"
              className="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)]"
            >
              <X size={18} weight="bold" />
            </button>
            {rail}
          </aside>
        </div>
      ) : null}
    </>
  );
}
