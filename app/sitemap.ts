import type { MetadataRoute } from "next";

import { SITE_ROUTES, SITE_URL } from "@/lib/site-map";

/**
 * /sitemap.xml: the public pages with one fixed address, from lib/site-map.ts.
 *
 * Reviews, questions, stores and profiles are left out for now — listing them
 * means reading every id from the API at request time, and a sitemap that
 * fails with the API would take the fixed pages down with it.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  return SITE_ROUTES.filter((route) => route.inSitemap).map((route) => ({
    url: route.path === "/" ? SITE_URL : `${SITE_URL}${route.path}`,
    changeFrequency: route.path === "/" || route.group === "Discover" || route.group === "Community" ? "daily" : "monthly",
    priority: route.path === "/" ? 1 : route.group === "Discover" || route.group === "Community" ? 0.8 : 0.5,
  }));
}
