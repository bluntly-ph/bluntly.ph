import Link from "next/link";
import { redirect } from "next/navigation";

import { logout } from "@/app/actions/auth";
import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { getUser } from "@/lib/dal";

/**
 * Home.
 *
 * Slice 1 covers the auth foundation only; the real landing page (hero,
 * search, trending, recent reviews, bottom nav) is Slice 2. Signed-out visitors
 * go straight to the welcome screen, which IS designed, rather than sitting on
 * a placeholder that is not.
 */
export default async function Home() {
  const user = await getUser();
  if (!user) redirect("/welcome");

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[430px] flex-col gap-6 bg-[var(--surface-app)] px-8 py-8">
      <header className="flex items-center justify-between">
        <span className="text-[var(--accent-primary)]">
          <Logo height={22} label="bluntly" />
        </span>
        <form action={logout}>
          <Button type="submit" variant="secondary" size="sm">
            Log out
          </Button>
        </form>
      </header>

      <section>
        <h1 className="text-[32px] font-bold leading-[1.15] text-[var(--text-primary)]">
          Finally.
          <br />
          Honest reviews<span className="text-[var(--accent-primary)]">.</span>
        </h1>
        <p className="mt-2 text-[14px] text-[var(--text-secondary)]">
          No sponsorships. No bias. Ever.
        </p>
      </section>

      <section className="rounded-[var(--radius-sm)] bg-white p-5 shadow-[var(--shadow-card)]">
        <div className="flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
            {`@${user.username ?? "—"}`}
          </h2>
          <span className="rounded-full bg-[color-mix(in_srgb,var(--accent-primary)_12%,transparent)] px-3 py-1 text-[11px] text-[var(--accent-primary)]">
            {`Level ${user.trust_stage}`}
          </span>
        </div>
        <dl className="mt-4 flex flex-col gap-2 text-[13px]">
          <div className="flex justify-between">
            <dt className="text-[var(--text-secondary)]">Email</dt>
            <dd className="text-[var(--text-primary)]">{user.email}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-[var(--text-secondary)]">Trust level</dt>
            <dd className="text-[var(--text-primary)]">
              {user.trust_level_name ?? `Stage ${user.trust_stage}`}
            </dd>
          </div>
          {user.interests?.length ? (
            <div className="flex justify-between gap-4">
              <dt className="shrink-0 text-[var(--text-secondary)]">Interests</dt>
              <dd className="text-right text-[var(--text-primary)]">
                {user.interests.join(", ")}
              </dd>
            </div>
          ) : null}
        </dl>
        <div className="mt-5">
          <Link href="/onboarding" className="contents">
            <Button variant="secondary" size="sm">
              Edit profile
            </Button>
          </Link>
        </div>
      </section>
    </main>
  );
}
