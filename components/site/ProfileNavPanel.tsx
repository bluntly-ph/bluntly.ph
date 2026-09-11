"use client";

import Image from "next/image";
import { createPortal } from "react-dom";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import {
  ChatCenteredDots,
  Compass,
  List,
  Gauge,
  Moon,
  PencilSimpleLine,
  Sun,
  Trophy,
  UserCircle,
  X,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";

import { setTheme } from "@/app/actions/auth";

/**
 * The navigation panel behind the header avatar.
 *
 * This replaces the mobile bottom navigation bar. The bottom bar's five
 * destinations implied a tab model the product does not have — it needed
 * dedicated screens per tab that are outside this delivery window — so the
 * owner's decision is one entry point (the avatar) opening a panel, and the
 * panel lists only destinations that genuinely exist.
 *
 * WHAT IS DELIBERATELY ABSENT: the design reference also lists "Bookmarks" and
 * "Recent reads". Neither has a route in this application. Linking them to `#`
 * or to a "coming soon" page would be a menu that lies about what the product
 * does, so they are omitted until the features exist. Dark mode IS here because
 * `setTheme` and the `data-theme` cookie are real.
 */

/**
 * The applied theme, read from the DOM rather than mirrored into state.
 *
 * `setState` inside an effect is a lint error in this project (it schedules a
 * cascading render), and the server already stamps `data-theme` from the
 * cookie — so the DOM is the source of truth and this is the sanctioned way to
 * subscribe to it. With no cookie the attribute is absent and CSS decides, so
 * the snapshot falls through to the media query.
 */
const themeListeners = new Set<() => void>();

function subscribeTheme(cb: () => void) {
  themeListeners.add(cb);
  return () => {
    themeListeners.delete(cb);
  };
}

function isDarkSnapshot(): boolean {
  const stamped = document.documentElement.dataset.theme;
  if (stamped === "dark") return true;
  if (stamped === "light") return false;
  return Boolean(window.matchMedia?.("(prefers-color-scheme: dark)").matches);
}

function applyTheme(next: "light" | "dark") {
  document.documentElement.dataset.theme = next;
  themeListeners.forEach((cb) => cb());
}

type Item = { href: string; icon: Icon; label: string };

const GROUPS: Item[][] = [
  [
    { href: "/profile", icon: UserCircle, label: "Profile" },
    { href: "/dashboard", icon: Gauge, label: "Dashboard" },
  ],
  [
    { href: "/reviews/new", icon: PencilSimpleLine, label: "Write a review" },
    { href: "/requests/new", icon: PencilSimpleLine, label: "Request review" },
    { href: "/requests", icon: Trophy, label: "Bounty board" },
    { href: "/categories", icon: Compass, label: "Categories" },
  ],
];

/**
 * Shown to everyone. The header's own links are `hidden … md:inline-flex`, and
 * the mobile bottom bar that used to carry them is gone — so without these a
 * signed-out visitor on a phone could reach the feed, categories, Q&A and the
 * bounty board from nowhere in the site chrome. Every route here exists.
 */
const PUBLIC_GROUP: Item[] = [
  { href: "/feed", icon: Compass, label: "Browse reviews" },
  { href: "/categories", icon: Compass, label: "Categories" },
  { href: "/questions", icon: ChatCenteredDots, label: "Q&A" },
  { href: "/requests", icon: Trophy, label: "Bounty board" },
];

export type PanelUser = { username: string | null; avatarUrl: string | null } | null;

export function ProfileNavPanel({ user }: { user: PanelUser }) {
  // Derived, not an effect: the panel is open only while the route it was
  // opened on is still the current one, so navigating closes it without a
  // pathname effect calling setState.
  const pathname = usePathname();
  const [openedOn, setOpenedOn] = useState<string | null>(null);
  const open = openedOn !== null && openedOn === pathname;
  const dark = useSyncExternalStore(subscribeTheme, isDarkSnapshot, () => false);
  const panelId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const close = useCallback(() => {
    setOpenedOn(null);
    triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
    };
    document.addEventListener("keydown", onKey);
    // Body scroll is locked while the sheet is open, and restored to whatever
    // it was — not hardcoded to "", which would clobber another lock.
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Move focus into the panel so a keyboard user is not left behind it.
    const first = panelRef.current?.querySelector<HTMLElement>("a, button");
    first?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, close]);

  async function toggleTheme() {
    const next: "light" | "dark" = dark ? "light" : "dark";
    // Paint immediately, then persist. Waiting for the server action would
    // leave the control looking broken for the length of a round trip.
    applyTheme(next);
    try {
      await setTheme(next);
    } catch {
      /* the cookie is a preference; a failure is not worth interrupting for */
    }
  }

  const initial = (user?.username ?? "?").slice(0, 1).toUpperCase();
  const groups = user ? [...GROUPS, PUBLIC_GROUP] : [PUBLIC_GROUP];

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpenedOn((v) => (v === null ? pathname : null))}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-haspopup="dialog"
        aria-label={user ? "Menu and profile" : "Menu"}
        className="relative grid h-10 w-10 shrink-0 cursor-pointer place-items-center overflow-hidden rounded-full bg-[var(--base-gray-200)] ring-1 ring-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
      >
        {user ? (
          user.avatarUrl ? (
            <Image src={user.avatarUrl} alt="" fill sizes="40px" className="object-cover" />
          ) : (
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              {initial}
            </span>
          )
        ) : (
          <List size={20} weight="bold" className="text-[var(--text-primary)]" />
        )}
      </button>

      {open
        ? createPortal(
            /* CRITICAL: portalled to <body> on purpose. The site header is
               `backdrop-blur-md`, and a non-`none` backdrop-filter makes an
               element the containing block for its `fixed` descendants — so
               rendering in place resolved `fixed inset-y-0` against the 64px
               header box and the sheet came out as an unusable 64px strip with
               a backdrop covering only the header. Measured in Chromium:
               844px tall without the blur, 64px with it. */
            <>
          {/* The backdrop closes, and is not a link: a stray tap on it must not
              navigate anywhere. */}
          <button
            type="button"
            aria-label="Close menu"
            onClick={close}
            className="fixed inset-0 z-40 cursor-default bg-[rgba(32,32,32,0.32)]"
          />
          <div
            ref={panelRef}
            id={panelId}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation and profile"
            className="fixed inset-y-0 right-0 z-50 flex w-[min(20rem,88vw)] flex-col overflow-y-auto bg-[var(--surface-card)] shadow-[var(--shadow-sheet)]"
          >
            <div className="flex items-start gap-3 p-5">
              {user ? (
              <span className="relative grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-full bg-[var(--base-gray-200)]">
                {user?.avatarUrl ? (
                  <Image src={user.avatarUrl} alt="" fill sizes="48px" className="object-cover" />
                ) : (
                  <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                    {initial}
                  </span>
                )}
              </span>
              ) : null}
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] font-semibold text-[var(--text-primary)]">
                  {user ? (user.username ?? "Your account") : "Menu"}
                </span>
                {user ? (
                  <span className="block text-[12px] text-[var(--text-secondary)]">
                    Member
                  </span>
                ) : null}
              </span>
              <button
                type="button"
                onClick={close}
                aria-label="Close menu"
                className="grid h-9 w-9 shrink-0 cursor-pointer place-items-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
              >
                <X size={18} />
              </button>
            </div>

            <nav aria-label="Primary" className="flex flex-col pb-2">
              {groups.map((group, gi) => (
                <div
                  key={gi}
                  className="border-t border-[var(--line-hairline-10)] py-2"
                >
                  {group.map(({ href, icon: Icon, label }) => (
                    <Link
                      key={href}
                      href={href}
                      className="flex items-center gap-3 px-5 py-3 text-[14px] text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
                    >
                      <Icon size={20} className="shrink-0 text-[var(--text-secondary)]" />
                      {label}
                    </Link>
                  ))}
                </div>
              ))}

              {!user ? (
                <div className="border-t border-[var(--line-hairline-10)] p-4">
                  <Link
                    href="/login"
                    className="flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] text-[14px] font-semibold text-white no-underline"
                  >
                    Log in
                  </Link>
                </div>
              ) : null}

              <div className="border-t border-[var(--line-hairline-10)] py-2">
                <button
                  type="button"
                  onClick={toggleTheme}
                  aria-pressed={dark}
                  className="flex w-full cursor-pointer items-center gap-3 px-5 py-3 text-left text-[14px] text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
                >
                  {dark ? (
                    <Sun size={20} className="shrink-0 text-[var(--text-secondary)]" />
                  ) : (
                    <Moon size={20} className="shrink-0 text-[var(--text-secondary)]" />
                  )}
                  Dark mode
                  <span
                    aria-hidden="true"
                    className={`ml-auto inline-flex h-6 w-10 items-center rounded-full p-0.5 transition-colors ${
                      dark ? "bg-[var(--accent-primary)]" : "bg-[var(--base-gray-200)]"
                    }`}
                  >
                    <span
                      className={`h-5 w-5 rounded-full bg-white transition-transform ${
                        dark ? "translate-x-4" : ""
                      }`}
                    />
                  </span>
                </button>
              </div>
            </nav>
          </div>
            </>,
            document.body,
          )
        : null}
    </>
  );
}

export default ProfileNavPanel;
