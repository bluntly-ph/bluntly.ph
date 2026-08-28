"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  CaretLeft,
  Cube,
  Fingerprint,
  Gear,
  Handbag,
  Link as LinkIcon,
  List,
  ListChecks,
  PiggyBank,
  Question,
  Storefront,
  UsersThree,
  X,
} from "@phosphor-icons/react/dist/ssr";

/**
 * The console's navigation, built to the sidebar component (5017:2225).
 *
 * That component has two states — a collapsed icon rail and an expanded rail
 * with labels, sectioned MAIN / MANAGE / FINANCE / SYSTEM — so the toggle is
 * part of the design, not an addition.
 *
 * Every item routes somewhere real. Two are deliberately inert and say why on
 * their face rather than being silently clickable:
 *
 *   Sellers    FR-4 was descoped by the owner (2026-07-28, reaffirmed
 *              2026-08-07) and the schema was dropped in migration 0024.
 *              There is no seller entity to manage.
 *   Settings   No console settings have been specified. Inventing some would
 *              be scope, not implementation.
 *
 * `Review Queue`, `Q&A` and reports are one screen with tabs, because frame
 * 5017:3758 draws them that way: Reviews / Answers / Report / Support.
 */

export type NavItem = {
  label: string;
  Icon: typeof Cube;
  href?: string;
  /** Matches when the path starts with this, for nested routes. */
  match?: string;
  /** Set when the item is intentionally inert; shown to the moderator. */
  blocked?: string;
};

export const NAV: { heading: string; items: NavItem[] }[] = [
  {
    heading: "Main",
    items: [
      { label: "Overview", Icon: Cube, href: "/moderate", match: "/moderate$" },
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
      { label: "Products", Icon: Handbag, href: "/moderate/products", match: "/moderate/products" },
      {
        label: "Sellers",
        Icon: Storefront,
        blocked:
          "Seller accounts were descoped by the owner; the schema was dropped in migration 0024.",
      },
      {
        label: "Reviewers",
        Icon: UsersThree,
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
        label: "Activity Log",
        Icon: Fingerprint,
        href: "/moderate/activity",
        match: "/moderate/activity",
      },
      {
        label: "Settings",
        Icon: Gear,
        blocked: "No console settings have been specified yet.",
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
      <div className={`flex items-center gap-2 px-4 pb-5 pt-5 ${collapsed ? "justify-center px-0" : ""}`}>
        {collapsed ? (
          <span className="font-[family-name:var(--font-display)] text-[20px] font-bold leading-none text-[var(--accent-primary)]">
            b
          </span>
        ) : (
          <span className="min-w-0">
            <span className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--accent-trust)]">
              Admin
            </span>
            <span className="block font-[family-name:var(--font-display)] text-[22px] font-bold leading-none text-[var(--accent-primary)]">
              bluntly
            </span>
          </span>
        )}
      </div>

      {/* The rail scrolls on its own only if the viewport is too short for the
          items. It never moves because the workspace scrolled. */}
      <nav aria-label="Admin sections" className="min-h-0 flex-1 overflow-y-auto px-2">
        {NAV.map((group) => (
          <div key={group.heading} className="mb-4">
            {!collapsed ? (
              <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
                {group.heading}
              </p>
            ) : (
              <hr className="mx-3 mb-2 border-[var(--border-subtle)]" />
            )}
            <ul className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const { label, Icon, href, blocked } = item;
                const active = isActive(item, pathname, tab);
                const base = `flex items-center gap-2.5 rounded-[var(--radius-sm)] px-3 py-2 text-[14px] font-medium ${
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
                            ? "bg-[var(--line-hairline-10)] text-[var(--accent-primary)]"
                            : "text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)]"
                        }`}
                      >
                        <Icon size={20} weight={active ? "fill" : "regular"} className="shrink-0" />
                        {!collapsed ? <span className="truncate">{label}</span> : null}
                      </Link>
                    ) : (
                      <span
                        title={blocked}
                        aria-disabled="true"
                        className={`${base} cursor-not-allowed text-[var(--text-muted)]`}
                      >
                        <Icon size={20} weight="regular" className="shrink-0" />
                        {!collapsed ? (
                          <>
                            <span className="truncate">{label}</span>
                            <span className="ml-auto shrink-0 rounded-[var(--radius-pill)] bg-[var(--surface-app)] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide">
                              n/a
                            </span>
                          </>
                        ) : null}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div
        className={`m-2 flex items-center gap-3 rounded-[var(--radius-sm)] p-2.5 shadow-[var(--shadow-hairline-inset)] ${
          collapsed ? "justify-center" : ""
        }`}
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--accent-primary)] text-[13px] font-bold text-[var(--text-on-brand)]">
          {moderator.name.slice(0, 1).toUpperCase()}
        </span>
        {!collapsed ? (
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-semibold text-[var(--text-primary)]">
              {moderator.name}
            </span>
            <span className="block text-[12px] capitalize text-[var(--text-secondary)]">
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
        /* Clears the site's mobile tab bar, which is fixed to the bottom at the
           same z-index. At bottom-4 this sat underneath it, so on a phone a
           moderator had no way to reach any console screen but the one they
           were already on. */
        className="fixed bottom-[84px] left-4 z-50 grid h-11 w-11 place-items-center rounded-full bg-[var(--accent-primary)] text-[var(--text-on-brand)] shadow-[var(--shadow-fab)] lg:hidden"
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
