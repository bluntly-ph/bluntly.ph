import type { Metadata } from "next";

import { NotificationList } from "@/components/site/NotificationList";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { Unavailable } from "@/components/site/Unavailable";
import { requireUser } from "@/lib/dal";
import { getNotifications } from "@/lib/notifications";

export const metadata: Metadata = {
  title: "Notifications — bluntly",
};

/**
 * The account's notifications (FR-1 1.6). No frame in the reference pack draws
 * this screen, so it uses the site's own list language — the same rows and
 * hairlines as the Questions and Sellers lists — rather than an invented look.
 */
export default async function NotificationsPage() {
  // Reading your own notifications needs a session, not a finished profile.
  const me = await requireUser();
  const items = await getNotifications(50);

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="mx-auto w-full max-w-[40rem] flex-1 px-6 py-8 lg:py-10">
        <h1 className="text-[22px] font-bold text-[var(--text-primary)]">Notifications</h1>
        {items === null ? <Unavailable what="notifications" /> : <NotificationList initial={items} />}
      </main>
      <SiteFooter />
    </div>
  );
}
