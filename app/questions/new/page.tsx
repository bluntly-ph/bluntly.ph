import type { Metadata } from "next";

import { AskQuestionForm } from "@/components/qa/AskQuestionForm";
import { requireOnboardedUser } from "@/lib/dal";

export const metadata: Metadata = {
  title: "Ask a question — bluntly",
};

export default async function NewQuestionPage() {
  const me = await requireOnboardedUser();
  return (
    // No SiteHeader, as on /reviews/new and /sellers/rate: the "Question Page"
    // step frames draw the composer's own header. No background of its own
    // either, so the composer's graph paper shows (ComposerGrid).
    <div className="flex min-h-dvh flex-col">
      <AskQuestionForm user={{ username: me.username, avatarUrl: me.avatar_url }} />
    </div>
  );
}
