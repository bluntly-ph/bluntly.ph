import type { Metadata } from "next";
import Link from "next/link";

import { RequestForm } from "@/components/requests/RequestForm";
import { RAIL_ACTION, RailGroup } from "@/components/site/BrowseRails";
import { SiteHeader } from "@/components/site/SiteHeader";
import { requireOnboardedUser } from "@/lib/dal";

export const metadata: Metadata = {
  title: "Post a request — bluntly",
};

export default async function NewRequestPage() {
  const me = await requireOnboardedUser();
  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url, role: me.role }} />
      {/* WEBSITE (`lg` and up): the form keeps a form's measure and what the
          board does with a request is said beside it, not buried under it. */}
      <main className="mx-auto w-full max-w-[40rem] flex-1 px-6 py-8 lg:grid lg:max-w-[64rem] lg:grid-cols-[minmax(0,34rem)_16rem] lg:items-start lg:gap-12 lg:px-10 lg:py-10">
        <RequestForm />
        <aside className="mt-10 border-t border-[var(--line-hairline-10)] pt-8 lg:mt-0 lg:border-0 lg:pt-0">
          <RailGroup title="What happens next">
            <p className="mt-3 text-[13px] leading-[20px] text-[var(--text-secondary)]">
              Your request joins the board. Other buyers up-vote what they want read, and reviewers pick from
              the top of it.
            </p>
            <ul className="mt-3 flex flex-col gap-2 text-[13px]">
              <li>
                <Link href="/requests" className={RAIL_ACTION}>
                  See the board
                </Link>
              </li>
              <li>
                <Link href="/search" className={RAIL_ACTION}>
                  Check it is not already reviewed
                </Link>
              </li>
            </ul>
          </RailGroup>
        </aside>
      </main>
    </div>
  );
}
