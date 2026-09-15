import type { Metadata } from "next";

import { requireOnboardedUser } from "@/lib/dal";

import { WriteReviewForm } from "./WriteReviewForm";

export const metadata: Metadata = {
  title: "Write a review — bluntly",
};

export default async function NewReviewPage() {
  // Writing requires an account; requireUser redirects to /login otherwise.
  const me = await requireOnboardedUser();
  return (
    // No SiteHeader: the reviewer frames draw a composer-specific header — a
    // back arrow and the avatar — and the form owns it, because only the form
    // knows what "back" means at each step.
    <div className="flex min-h-dvh flex-col">
      <WriteReviewForm user={{ username: me.username, avatarUrl: me.avatar_url }} />
    </div>
  );
}
