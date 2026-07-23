import Link from "next/link";

import { logout } from "@/app/actions/auth";
import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { getUser } from "@/lib/dal";

/**
 * Placeholder home.
 *
 * Slice 1 is the auth foundation; the real landing page (hero, search, trending,
 * recent reviews) is Slice 2. This exists so the auth flow has somewhere to land
 * and so session state is visible end-to-end.
 */
export default async function Home() {
  const user = await getUser();

  return (
    <main className="mx-auto flex w-full max-w-[960px] flex-1 flex-col gap-8 px-8 py-10">
      <header className="flex items-center justify-between">
        <Logo size={28} />
        {user ? (
          <form action={logout}>
            <Button type="submit" variant="secondary" size="sm">
              Log out
            </Button>
          </form>
        ) : (
          <div className="flex gap-3">
            <Link href="/login">
              <Button variant="secondary" size="sm">
                Log in
              </Button>
            </Link>
            <Link href="/signup">
              <Button size="sm">Sign up</Button>
            </Link>
          </div>
        )}
      </header>

      <section className="flex flex-col gap-3">
        <h1 className="text-[length:var(--text-3xl)] font-bold leading-tight text-[var(--text-primary)]">
          Finally. Honest reviews.
        </h1>
        <p className="text-[length:var(--text-sm)] text-[var(--text-secondary)]">
          No sponsorships. No bias. Ever.
        </p>
      </section>

      {user ? (
        <section className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-6 shadow-[var(--shadow-card)]">
          <h2 className="text-[length:var(--text-lg)] font-medium text-[var(--text-primary)]">
            {`Signed in as @${user.username ?? "—"}`}
          </h2>
          <dl className="mt-4 grid grid-cols-2 gap-y-2 text-[length:var(--text-xs)]">
            <dt className="text-[var(--text-secondary)]">Email</dt>
            <dd className="text-[var(--text-primary)]">{user.email}</dd>
            <dt className="text-[var(--text-secondary)]">Trust level</dt>
            <dd className="text-[var(--text-primary)]">
              {user.trust_level_name ?? `Stage ${user.trust_stage}`}
            </dd>
            <dt className="text-[var(--text-secondary)]">Role</dt>
            <dd className="text-[var(--text-primary)]">{user.role}</dd>
          </dl>
          <div className="mt-6">
            <Link href="/onboarding">
              <Button variant="ghost" size="sm">
                Edit profile
              </Button>
            </Link>
          </div>
        </section>
      ) : null}
    </main>
  );
}
