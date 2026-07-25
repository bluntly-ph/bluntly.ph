import type { ReactNode } from "react";

import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getUser } from "@/lib/dal";

/**
 * Chrome for standalone content pages (About, How it works, Terms, FAQs, …):
 * the site header carrying the viewer's auth state, a centered reading column,
 * and the footer. Async because the header needs the current user, read from the
 * httpOnly cookie server-side. `width="wide"` opts into the 72rem grid for
 * index-style pages; the default is a 46rem reading measure.
 */
export async function PageShell({
  children,
  width = "prose",
}: {
  children: ReactNode;
  width?: "prose" | "wide";
}) {
  let user: HeaderUser = null;
  try {
    const me = await getUser();
    user = me ? { username: me.username, avatarUrl: me.avatar_url } : null;
  } catch {
    user = null;
  }

  const max = width === "prose" ? "max-w-[46rem]" : "max-w-[72rem]";

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className={`mx-auto w-full flex-1 px-6 py-10 lg:px-10 lg:py-16 ${max}`}>
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}

export default PageShell;
