import Link from "next/link";

import { Logo } from "@/components/ui/Logo";

/**
 * Auth shell — one tree, both breakpoints.
 *
 * Mobile (< lg) reproduces the Figma frame: the brand gradient fills the screen,
 * the form rises as a rounded-top sheet with a grabber.
 * Desktop (>= lg) switches to the dark page with a centred card.
 *
 * This is CSS-driven rather than two component sets, so there is one DOM to keep
 * accessible and one place to fix a bug.
 */
export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="flex min-h-dvh flex-col bg-[image:var(--brand-gradient)] lg:bg-none lg:bg-[var(--surface-app)]">
      {/* Mobile hero: the wordmark sits on the gradient. */}
      <header className="flex flex-1 items-center justify-center lg:hidden">
        <Link href="/" aria-label="bluntly home">
          <Logo size={32} tone="inherit" className="text-white" />
        </Link>
      </header>

      {/* Desktop header bar. */}
      <header className="hidden lg:flex lg:items-center lg:justify-between lg:px-10 lg:py-5">
        <Link href="/" aria-label="bluntly home">
          <Logo size={24} />
        </Link>
      </header>

      <main
        className={[
          // Mobile: bottom sheet.
          "rounded-t-[var(--radius-pill)] bg-[var(--surface-app)] px-8 pb-10 pt-4",
          "shadow-[var(--shadow-sheet)]",
          // Desktop: centred card, no sheet affordance.
          "lg:mx-auto lg:mb-auto lg:mt-16 lg:w-full lg:max-w-[420px] lg:rounded-[var(--radius-sm)]",
          "lg:bg-[var(--surface-card)] lg:p-10 lg:shadow-[var(--shadow-card)]",
        ].join(" ")}
      >
        {/* Sheet grabber — a mobile affordance only, and decorative. */}
        <div
          aria-hidden="true"
          className="mx-auto mb-8 h-2 w-[120px] rounded-[var(--radius-sm)] bg-[var(--base-gray-200)] lg:hidden"
        />
        {children}
      </main>
    </div>
  );
}
