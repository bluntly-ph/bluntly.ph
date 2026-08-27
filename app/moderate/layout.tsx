import { Suspense } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import { requireRole } from "@/lib/dal";
import { getAdminOverview } from "@/lib/moderation";

/**
 * The console shell wraps every /moderate route.
 *
 * It lives in a layout rather than in each page so the rail and header are not
 * torn down and rebuilt on navigation: moving between Overview and the Review
 * Queue changes only the workspace, which is what makes it behave like an
 * application instead of a set of documents.
 *
 * The role check is here too, so every child route inherits it and none can be
 * added later that forgets it.
 */
export default async function ModerateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Redirects: to /login if signed out, to / if not a moderator.
  const me = await requireRole("moderator");
  const overview = await getAdminOverview();

  return (
    <Suspense fallback={null}>
      <AdminShell
        urgent={overview?.urgent ?? 0}
        moderator={{
          name: me.display_name ?? me.username ?? "Moderator",
          role: me.role ?? "moderator",
        }}
      >
        {children}
      </AdminShell>
    </Suspense>
  );
}
