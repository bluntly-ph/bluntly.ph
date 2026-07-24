import type { Metadata } from "next";

import { SiteHeader } from "@/components/site/SiteHeader";
import { requireUser } from "@/lib/dal";

import { WriteReviewForm } from "./WriteReviewForm";

export const metadata: Metadata = {
  title: "Write a review — bluntly",
};

export default async function NewReviewPage() {
  // Writing requires an account; requireUser redirects to /login otherwise.
  const me = await requireUser();
  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="flex-1">
        <WriteReviewForm />
      </main>
    </div>
  );
}
