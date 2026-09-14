import type { Metadata } from "next";

import { Hero } from "@/components/landing/Hero";
import { LandingCta } from "@/components/landing/LandingCta";
import { ReadingRail } from "@/components/landing/ReadingRail";
import { TrustSection } from "@/components/landing/TrustSection";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getUser } from "@/lib/dal";
import { getLandingReviews } from "@/lib/reviews";

export const metadata: Metadata = {
  title: "bluntly — Finally. Honest reviews.",
  description:
    "Philippine product reviews you can trust. No sponsorships. No bias. Ever.",
};

/**
 * Home — the public landing page.
 *
 * Anyone can read it without an account; the header shows "Log in" for signed-out
 * visitors and the avatar for signed-in ones. A backend outage must not take the
 * marketing page down, so a failure to resolve the user just means "signed out".
 */
export default async function Home() {
  // Parallel, not sequential: the viewer and the feed are independent, and
  // awaiting them in turn added a whole backend round trip to every visit.
  const [me, landing] = await Promise.all([
    getUser().catch(() => null),
    getLandingReviews(),
  ]);
  const user: HeaderUser = me
    ? { username: me.username, avatarUrl: me.avatar_url }
    : null;
  const { featured, cards } = landing;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="flex-1">
        <Hero featured={featured} />
        <ReadingRail reviews={cards} />
        <TrustSection />
        <LandingCta />
      </main>
      <SiteFooter />
    </div>
  );
}
