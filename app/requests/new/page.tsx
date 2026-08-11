import type { Metadata } from "next";

import { RequestForm } from "@/components/requests/RequestForm";
import { SiteHeader } from "@/components/site/SiteHeader";
import { requireOnboardedUser } from "@/lib/dal";
import { getTokenBalance } from "@/lib/tokens";

export const metadata: Metadata = {
  title: "Post a request — bluntly",
};

export default async function NewRequestPage() {
  // The gate has to resolve before the balance — the balance read is pointless
  // for someone who is about to be redirected — but they are otherwise
  // independent, so nothing else here needs to be sequential.
  const me = await requireOnboardedUser();
  const tokenBalance = await getTokenBalance();
  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="mx-auto w-full max-w-[40rem] flex-1 px-6 py-8 lg:py-10">
        <RequestForm tokenBalance={tokenBalance} />
      </main>
    </div>
  );
}
