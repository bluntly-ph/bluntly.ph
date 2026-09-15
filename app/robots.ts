import type { MetadataRoute } from "next";

import { PROTECTED, AUTH_ONLY } from "@/lib/route-access";
import { SITE_URL } from "@/lib/site-map";

/**
 * /robots.txt: crawl everything public, skip what needs a session or only
 * makes sense signed out (the same lists the proxy enforces), the API, and the
 * affiliate redirects — a crawler following /r/ would count as a click.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [...PROTECTED, "/sellers/*/dashboard", ...AUTH_ONLY, "/api/", "/r/"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
