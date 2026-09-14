import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, CaretRight, MagnifyingGlass, Star } from "@phosphor-icons/react/dist/ssr";

import { ActionMenu } from "@/components/site/ActionMenu";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getUser } from "@/lib/dal";
import { CATEGORIES } from "@/lib/landing-data";

export const metadata: Metadata = {
  title: "Categories — bluntly",
};

/**
 * Browse categories.
 *
 * Phone, built to "Categories.png" (390): its own 72px bar — back arrow, a
 * centred 16px "Categories", search — over a full-width #b4b4b4 rule, then a
 * list of 72px rows inset 24px: a 22px icon, the label in 16px bold 11px after
 * it, and #b4b4b4 dividers. From `md` up there is no frame, and the tile grid
 * stays.
 *
 * INTENTIONAL PRODUCT DIFFERENCES:
 *  - The frame ends each row with "+", an expander. No category has
 *    subcategories in this product, and "Subcategory.png" draws none, so a
 *    "+" would open nothing. Each row links to its category instead, with a
 *    trailing arrow that says so.
 *  - Labels follow the product's taxonomy, which reviews are stored against by
 *    slug: "Kids & Toys" and "Sports & Outdoors" where the frame writes "Kids &
 *    Baby" and "Outdoor & Sports", and "Audio", which the frame omits.
 *
 * "Recommended for you" is real: /feed ranks by the reader's chosen interests.
 */
export default async function CategoriesPage() {
  let user: HeaderUser = null;
  try {
    const me = await getUser();
    user = me ? { username: me.username, avatarUrl: me.avatar_url } : null;
  } catch {
    user = null;
  }

  const categories = CATEGORIES.filter((c) => c.slug !== "trending");
  const bar = "grid h-10 w-10 place-items-center rounded-full text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)]";
  const row = "flex h-[71px] items-center gap-[11px] pr-1 no-underline focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)]";

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <div className="hidden md:block">
        <SiteHeader user={user} />
      </div>

      <nav
        aria-label="Categories"
        className="sticky top-0 z-30 grid h-[72px] grid-cols-[40px_1fr_40px] items-center border-b border-[#b4b4b4] bg-[var(--surface-app)] px-4 md:hidden"
      >
        <Link href="/" aria-label="Back" className={bar}>
          <ArrowLeft size={26} />
        </Link>
        <h1 className="text-center text-[16px] text-[var(--text-primary)]">Categories</h1>
        <Link href="/search" aria-label="Search" className={bar}>
          <MagnifyingGlass size={26} />
        </Link>
      </nav>

      <main className="mx-auto w-full max-w-[72rem] flex-1 pb-8 md:px-6 md:py-8 lg:px-10 lg:py-10">
        <ul className="md:hidden">
          <li className="mx-6 border-b border-[#b4b4b4]">
            <Link href="/feed" className={row}>
              <Star size={22} aria-hidden="true" className="shrink-0 text-[var(--text-primary)]" />
              <span className="text-[16px] font-bold text-[var(--text-primary)]">Recommended for you</span>
              <CaretRight size={18} aria-hidden="true" className="ml-auto shrink-0 text-[var(--text-primary)]" />
            </Link>
          </li>
          {categories.map((c) => {
            const Icon = c.icon;
            return (
              <li key={c.slug} className="mx-6 border-b border-[#b4b4b4]">
                <Link href={`/search?category=${c.slug}&from=categories`} className={row}>
                  <Icon size={22} aria-hidden="true" className="shrink-0 text-[var(--text-primary)]" />
                  <span className="text-[16px] font-bold text-[var(--text-primary)]">{c.label}</span>
                  <CaretRight size={18} aria-hidden="true" className="ml-auto shrink-0 text-[var(--text-primary)]" />
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="hidden md:block">
          <h1 className="text-[24px] font-bold text-[var(--text-primary)]">Browse categories</h1>
          <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
            Honest reviews across everything Filipinos shop for.
          </p>

          <ul className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {categories.map((c) => {
              const Icon = c.icon;
              return (
                <li key={c.slug}>
                  <Link
                    // `from=categories` marks where the visitor came in from, so
                    // /search can offer a way back here instead of stranding them
                    // in search with no route to the index (BUG-011).
                    href={`/search?category=${c.slug}&from=categories`}
                    className="flex h-[104px] flex-col justify-between rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)] outline outline-1 outline-transparent transition-[outline-color] hover:outline-[var(--accent-primary)]"
                  >
                    <span className="grid h-10 w-10 place-items-center rounded-[10px] bg-[color-mix(in_srgb,var(--accent-primary)_10%,transparent)] text-[var(--accent-primary)]">
                      <Icon size={22} />
                    </span>
                    <span className="text-[14px] font-medium leading-tight text-[var(--text-primary)]">
                      {c.label}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </main>
      <ActionMenu />
      <SiteFooter />
    </div>
  );
}
