import type { Metadata } from "next";

import { requireUser } from "@/lib/dal";

import { OnboardingForm } from "./OnboardingForm";

export const metadata: Metadata = {
  title: "Set up your profile — bluntly",
};

export default async function OnboardingPage() {
  const user = await requireUser();
  return (
    <main className="mx-auto w-full max-w-[420px] px-8 py-12">
      <OnboardingForm currentUsername={user.username ?? ""} />
    </main>
  );
}
