"use client";

import { useState } from "react";
import { MagnifyingGlass, ShieldCheck, UserMinus, UserPlus } from "@phosphor-icons/react/dist/ssr";

type StaffUser = {
  id: string;
  staff_ref: string;
  display_name: string | null;
  username: string | null;
  email: string | null;
  role: "user" | "seller" | "moderator";
  is_super_admin: boolean;
  is_suspended: boolean;
  trust_stage: number;
  created_at: string;
};

type DirectoryPage = {
  rows: StaffUser[];
  total: number;
  resolved_staff_ref: string | null;
  can_manage_roles: boolean;
};

type Problem = { detail?: string };

/**
 * Staff account lookup and the deliberately narrower moderator-role control.
 *
 * The browser receives no access token: requests go through the same BFF as
 * every other interactive admin control. `can_manage_roles` only controls what
 * is offered; FastAPI re-loads the actor and authorizes every PATCH itself.
 */
export function UserManagement() {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState<DirectoryPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [changing, setChanging] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function findUsers(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const candidate = query.trim();
    if (!candidate) return;

    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(
        `/api/bff/api/v1/admin/users?q=${encodeURIComponent(candidate)}`,
        { cache: "no-store" },
      );
      if (!response.ok) {
        const problem = (await response.json().catch(() => ({}))) as Problem;
        throw new Error(problem.detail ?? "Search failed.");
      }
      setPage((await response.json()) as DirectoryPage);
    } catch (cause) {
      setPage(null);
      setError(cause instanceof Error ? cause.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  async function changeRole(user: StaffUser) {
    if (!page?.can_manage_roles || user.is_super_admin) return;
    const next = user.role === "moderator" ? "user" : "moderator";
    const verb = next === "moderator" ? "grant Moderator access to" : "revoke Moderator access from";
    const identity = user.display_name ?? user.username ?? user.staff_ref;
    if (!window.confirm(`Confirm: ${verb} ${identity}?`)) return;

    setChanging(user.id);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`/api/bff/api/v1/admin/users/${user.id}/role`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ role: next }),
      });
      if (!response.ok) {
        const problem = (await response.json().catch(() => ({}))) as Problem;
        throw new Error(problem.detail ?? "Role change failed.");
      }
      setPage((current) =>
        current
          ? {
              ...current,
              rows: current.rows.map((row) =>
                row.id === user.id ? { ...row, role: next } : row,
              ),
            }
          : current,
      );
      setNotice(
        next === "moderator"
          ? `${identity} is now a Moderator.`
          : `${identity} no longer has Moderator access.`,
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Role change failed.");
    } finally {
      setChanging(null);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <header className="shrink-0">
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">User management</h2>
        <p className="mt-1 max-w-[55rem] text-[13px] text-[var(--text-secondary)]">
          Find an account by staff reference, UUID, exact email, display name, or username.
          Staff references are internal and do not grant access to anything.
        </p>
      </header>

      <form
        role="search"
        onSubmit={(event) => void findUsers(event)}
        className="flex shrink-0 flex-col gap-2 rounded-[var(--radius-md)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)] sm:flex-row"
      >
        <label htmlFor="staff-user-query" className="sr-only">Find a platform user</label>
        <div className="relative min-w-0 flex-1">
          <MagnifyingGlass
            aria-hidden="true"
            size={18}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
          />
          <input
            id="staff-user-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="USR-000123, UUID, exact email, or name"
            maxLength={320}
            autoComplete="off"
            className="h-11 w-full rounded-[var(--radius-pill)] bg-[var(--surface-app)] pl-10 pr-4 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="h-11 rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-5 text-[13px] font-semibold text-[var(--text-on-brand)] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      <div aria-live="polite" className="min-h-5 shrink-0 text-[13px]">
        {error ? <p role="alert" className="text-[var(--accent-danger)]">{error}</p> : null}
        {notice ? <p role="status" className="text-[var(--accent-trust)]">{notice}</p> : null}
        {!error && !notice && page ? (
          <p className="text-[var(--text-secondary)]">
            {page.total} match{page.total === 1 ? "" : "es"}
            {page.resolved_staff_ref ? ` · resolved as ${page.resolved_staff_ref}` : ""}
          </p>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)]">
        {!page ? (
          <EmptyState text="Search for a user to inspect their administrative status." />
        ) : page.rows.length === 0 ? (
          <EmptyState text="No account matched that identifier." />
        ) : (
          <table className="w-full min-w-[54rem] border-collapse text-left">
            <thead className="sticky top-0 z-10 bg-[var(--surface-app)]">
              <tr className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
                <th className="px-4 py-3 font-medium">User</th>
                <th className="px-4 py-3 font-medium">Staff reference</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Joined</th>
                <th className="px-4 py-3 text-right font-medium">Access</th>
              </tr>
            </thead>
            <tbody>
              {page.rows.map((user) => {
                const managed = user.role === "user" || user.role === "moderator";
                return (
                  <tr key={user.id} className="border-t border-[var(--border-subtle)] text-[13px]">
                    <td className="px-4 py-3">
                      <span className="block font-medium text-[var(--text-primary)]">
                        {user.display_name ?? user.username ?? "Unnamed user"}
                      </span>
                      <span className="block text-[12px] text-[var(--text-muted)]">
                        {user.email ?? (user.username ? `@${user.username}` : user.id)}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[12px] font-semibold text-[var(--text-primary)]">
                      {user.staff_ref}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1.5 capitalize text-[var(--text-secondary)]">
                        {user.is_super_admin ? <ShieldCheck size={16} weight="fill" className="text-[var(--accent-primary)]" /> : null}
                        {user.is_super_admin ? "super admin" : user.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">
                      {user.is_suspended ? "Suspended" : `Active · trust ${user.trust_stage}`}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-[12px] text-[var(--text-muted)]">
                      {new Date(user.created_at).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {page.can_manage_roles && managed && !user.is_super_admin ? (
                        <button
                          type="button"
                          onClick={() => void changeRole(user)}
                          disabled={changing === user.id}
                          className="inline-flex min-h-9 items-center gap-1.5 rounded-[var(--radius-pill)] px-3 text-[12px] font-semibold text-[var(--accent-primary)] shadow-[var(--shadow-hairline-inset)] hover:bg-[var(--line-hairline-10)] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
                        >
                          {user.role === "moderator" ? <UserMinus size={15} /> : <UserPlus size={15} />}
                          {changing === user.id
                            ? "Saving…"
                            : user.role === "moderator"
                              ? "Revoke Moderator"
                              : "Make Moderator"}
                        </button>
                      ) : (
                        <span className="text-[12px] text-[var(--text-muted)]">
                          {page.can_manage_roles ? "Not managed here" : "View only"}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="grid min-h-48 place-items-center p-8 text-center text-[13px] text-[var(--text-secondary)]">
      <p>{text}</p>
    </div>
  );
}
