import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getUser } from "@/lib/dal";
import { CATEGORIES } from "@/lib/landing-data";

export const metadata: Metadata = {
  title: "Categories — bluntly",
};

export default async function CategoriesPage() {
  let user: HeaderUser = null;
  try {
    const me = await getUser();
    user = me ? { username: me.username, avatarUrl: me.avatar_url } : null;
  } catch {
    user = null;
  }

  const categories = CATEGORIES.filter((c) => c.slug !== "trending");

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto w-full max-w-[72rem] flex-1 px-6 py-8 lg:px-10 lg:py-10">
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
                  href={`/search?category=${c.slug}`}
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
      </main>
      <SiteFooter />
    </div>
  );
}
