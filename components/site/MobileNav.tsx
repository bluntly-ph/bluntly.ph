"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChatCenteredDots,
  House,
  MagnifyingGlass,
  Plus,
  UserCircle,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";

/** Routes with their own full-screen chrome — no app bottom nav there. */
const HIDDEN_ON = ["/welcome", "/login", "/signup", "/onboarding"];

type Item = { href: string; icon: Icon; label: string; primary?: boolean };

const ITEMS: Item[] = [
  { href: "/", icon: House, label: "Home" },
  { href: "/search", icon: MagnifyingGlass, label: "Search" },
  { href: "/reviews/new", icon: Plus, label: "Write", primary: true },
  { href: "/requests", icon: ChatCenteredDots, label: "Requests" },
  { href: "/profile", icon: UserCircle, label: "You" },
];

/**
 * The mobile bottom navigation from the Figma (hidden at `lg` where the header
 * carries the links). A spacer reserves room so fixed content never hides the
 * page's footer. Self-hides on the letterboxed auth/onboarding screens.
 */
export function MobileNav() {
  const pathname = usePathname();
  if (HIDDEN_ON.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return null;
  }

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <>
      <div aria-hidden="true" className="h-[68px] lg:hidden" />
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-40 flex items-stretch justify-around border-t border-[var(--border-subtle)] bg-[var(--surface-card)] pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        {ITEMS.map(({ href, icon: Icon, label, primary }) => {
          const active = isActive(href);
          if (primary) {
            return (
              <Link
                key={href}
                href={href}
                aria-label={label}
                className="flex flex-1 items-center justify-center py-2"
              >
                <span className="grid h-11 w-11 -translate-y-3 place-items-center rounded-full bg-[var(--accent-primary)] text-white shadow-[var(--shadow-fab)]">
                  <Icon size={24} weight="bold" />
                </span>
              </Link>
            );
          }
          return (
            <Link
              key={href}
              href={href}
              className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[10px] ${
                active ? "text-[var(--accent-primary)]" : "text-[var(--text-muted)]"
              }`}
            >
              <Icon size={22} weight={active ? "fill" : "regular"} />
              {label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}

export default MobileNav;
