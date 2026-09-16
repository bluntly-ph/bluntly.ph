import type { Metadata } from "next";

import Link from "next/link";

import { NotificationList } from "@/components/site/NotificationList";
import { RAIL_ACTION, RailGroup } from "@/components/site/BrowseRails";
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
 *
 * WEBSITE (`lg` and up): the list keeps its reading measure and the account's
 * other destinations sit beside it, so a monitor shows a page rather than a
 * narrow strip of notices.
 */
export default async function NotificationsPage() {
  // Reading your own notifications needs a session, not a finished profile.
  const me = await requireUser();
  const items = await getNotifications(50);

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url }} />
      <main className="mx-auto w-full max-w-[40rem] flex-1 px-6 py-8 lg:grid lg:max-w-[64rem] lg:grid-cols-[minmax(0,38rem)_14rem] lg:items-start lg:gap-12 lg:px-10 lg:py-10">
        <div className="min-w-0">
          <h1 className="text-[22px] font-bold text-[var(--text-primary)]">Notifications</h1>
          {items === null ? <Unavailable what="notifications" /> : <NotificationList initial={items} />}
        </div>
        <aside className="mt-10 border-t border-[var(--line-hairline-10)] pt-8 lg:mt-0 lg:border-0 lg:pt-0">
          <RailGroup title="Your account">
            <ul className="mt-3 flex flex-col gap-2 text-[13px]">
              <li>
                <Link href="/profile" className={RAIL_ACTION}>
                  Profile
                </Link>
              </li>
              <li>
                <Link href="/dashboard" className={RAIL_ACTION}>
                  Earnings
                </Link>
              </li>
              <li>
                <Link href="/dashboard/reviews" className={RAIL_ACTION}>
                  Your reviews
                </Link>
              </li>
            </ul>
          </RailGroup>
        </aside>
      </main>
      <SiteFooter />
    </div>
  );
}
