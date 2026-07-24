import type { Metadata } from "next";

import { RequestForm } from "@/components/requests/RequestForm";
import { SiteHeader } from "@/components/site/SiteHeader";
import { requireUser } from "@/lib/dal";

export const metadata: Metadata = {
  title: "Post a request — bluntly",
};

export default async function NewRequestPage() {
  const me = await requireUser();
  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="mx-auto w-full max-w-[40rem] flex-1 px-6 py-8 lg:py-10">
        <RequestForm />
      </main>
    </div>
  );
}
