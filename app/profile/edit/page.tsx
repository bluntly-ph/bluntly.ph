import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "@phosphor-icons/react/dist/ssr";

import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { requireOnboardedUser } from "@/lib/dal";

import { EditProfileForm } from "./EditProfileForm";

export const metadata: Metadata = {
  title: "Edit your profile — bluntly",
};

/**
 * Edit profile — a real edit screen, not the onboarding wizard (BUG-035).
 *
 * `/profile`'s Edit chip pointed at `/onboarding`, so changing a display name
 * meant walking back through a four-step introduction to a site the member has
 * been using for months, with their interests blank as though they had never
 * chosen any. See `EditProfileForm` for why pre-filling the wizard would have
 * been the wrong fix.
 *
 * `requireOnboardedUser` rather than `requireUser`: someone who has not
 * finished onboarding belongs in onboarding, and this route must not become a
 * way around it.
 */
export default async function EditProfilePage() {
  const me = await requireOnboardedUser();

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={{ username: me.username, avatarUrl: me.avatar_url, role: me.role }} />
      <main className="mx-auto w-full max-w-[42rem] flex-1 px-4 pb-16 pt-5 md:px-6 md:pt-10">
        <Link
          href="/profile"
          className="inline-flex items-center gap-1 text-[12px] font-light leading-none text-[var(--text-primary)] no-underline hover:text-[var(--accent-primary)]"
        >
          <ArrowLeft size={16} aria-hidden="true" /> Your profile
        </Link>

        <h1 className="mt-5 text-[24px] font-semibold leading-none text-[var(--text-primary)]">
          Edit your profile
        </h1>
        <p className="mt-3 text-[14px] font-light leading-[21px] text-[rgba(32,32,32,0.7)]">
          Everything here is already filled in with what you have now. Change what
          you want and save — nothing else moves.
        </p>

        <div className="mt-8">
          <EditProfileForm
            username={me.username ?? ""}
            displayName={me.display_name ?? ""}
            avatarUrl={me.avatar_url}
            interests={me.interests ?? []}
          />
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
