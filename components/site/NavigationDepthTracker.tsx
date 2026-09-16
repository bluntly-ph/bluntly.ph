"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { recordPath } from "@/lib/navigation-depth";

/**
 * Feeds `lib/navigation-depth` the app's route changes (BUG-033).
 *
 * Mounted once, in the root layout, because the layout is the one component
 * that survives every navigation — a page-level tracker would be unmounted and
 * replaced along with the page it sits on, and start counting from zero each
 * time.
 *
 * Pathname only, not the query. `useSearchParams` in the root layout opts
 * every route out of static rendering, and skipping query-only changes can only
 * make the depth too LOW — which `BackControl` handles by falling back to a real
 * link, never by leaving the site. See the module for why that direction is the
 * safe one.
 *
 * Renders nothing.
 */
export function NavigationDepthTracker() {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname) recordPath(pathname);
  }, [pathname]);

  return null;
}

export default NavigationDepthTracker;
