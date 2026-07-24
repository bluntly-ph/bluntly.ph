import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ReviewDetail } from "@/components/review/ReviewDetail";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getUser } from "@/lib/dal";
import { getReviewFull } from "@/lib/reviews";

export const metadata: Metadata = {
  title: "Review — bluntly",
};

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await getReviewFull(id);
  if (!data) notFound();

  let user: HeaderUser = null;
  let canVote = false;
  try {
    const me = await getUser();
    if (me) {
      user = { username: me.username, avatarUrl: me.avatar_url };
      // You may vote on any published review except your own.
      canVote = me.id !== data.author?.id;
    }
  } catch {
    user = null;
  }

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="flex-1">
        <ReviewDetail data={data} canVote={canVote} />
      </main>
      <SiteFooter />
    </div>
  );
}
