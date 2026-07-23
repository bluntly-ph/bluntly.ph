import type { Metadata } from "next";

import { requireUser } from "@/lib/dal";

import { OnboardingWizard } from "./OnboardingWizard";

export const metadata: Metadata = {
  title: "Set up your profile — bluntly",
};

export default async function OnboardingPage() {
  const user = await requireUser();
  return (
    <OnboardingWizard
      user={{
        username: user.username ?? "",
        avatarUrl: user.avatar_url,
        trustLevelName: user.trust_level_name ?? "Newcomer",
        trustStage: user.trust_stage,
        verifiedReviewCount: user.verified_review_count ?? 0,
      }}
    />
  );
}
