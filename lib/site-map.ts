/**
 * Every page on bluntly.ph, in one list.
 *
 * It is the answer to "what pages do we have": the source of /sitemap.xml
 * (public pages only), of docs/SITEMAP.md (all of them, with who can open each
 * and where its design comes from), and the list a full-site check walks.
 * tests/frontend/site-map.test.mjs fails if a page exists without an entry, an
 * entry outlives its page, or a declared access level is not what the proxy
 * enforces — so the map cannot quietly go stale.
 *
 * `figma` names the frames a page is built to, from the file's own frame names
 * and node ids. `null` means the file draws no screen for it: a product or
 * business page kept from the PRD and dressed in the Figma system's language.
 *
 * No imports: the test runs this file directly under Node.
 */

export const SITE_URL = "https://www.bluntly.ph";

export type Access =
  /** Anyone, signed in or not. */
  | "public"
  /** Signed-out visitors only; the proxy sends a signed-in reader home. */
  | "signed-out"
  /** Needs a session; the proxy sends a signed-out visitor to /login?next=. */
  | "signed-in"
  /** Needs a session and the moderator role (app/moderate/layout.tsx). */
  | "moderator"
  /** Needs a session; only the store's approved owner sees its figures. */
  | "store-owner";

export type Group =
  | "Discover"
  | "Community"
  | "Write"
  | "Sign in"
  | "Account"
  | "Earnings"
  | "Company"
  | "Legal"
  | "Moderation";

export type SiteRoute = {
  /** The URL pattern, with dynamic segments in brackets as the app names them. */
  path: string;
  /** The page file that serves it. */
  file: string;
  title: string;
  group: Group;
  access: Access;
  purpose: string;
  figma: string | null;
  /** Listed in /sitemap.xml: public, one fixed URL, worth a search engine's time. */
  inSitemap: boolean;
};

export const SITE_ROUTES: SiteRoute[] = [
  // ------------------------------------------------------------------ Discover
  {
    path: "/",
    file: "app/page.tsx",
    title: "Landing",
    group: "Discover",
    access: "public",
    purpose: "The front door: what bluntly is, the ask-anything search, a featured review and the trust story.",
    figma: "Mobile Landing Page (1902:1504)",
    inSitemap: true,
  },
  {
    path: "/search",
    file: "app/search/page.tsx",
    title: "Search",
    group: "Discover",
    access: "public",
    purpose: "Search reviews, questions and sellers in tabs, with filters, sort and recent searches. Has the + action button.",
    figma: "Mobile Search Page for Buyers / Reviewers / Sellers (3481:1776, 3481:1894, 3954:650), All filters, Sort",
    inSitemap: true,
  },
  {
    path: "/categories",
    file: "app/categories/page.tsx",
    title: "Categories",
    group: "Discover",
    access: "public",
    purpose: "Browse every product category; a category opens search filtered to it.",
    figma: "Categories (2355:939), Subcategory (2355:2267)",
    inSitemap: true,
  },
  {
    path: "/feed",
    file: "app/feed/page.tsx",
    title: "Feed",
    group: "Discover",
    access: "public",
    purpose: "The browsing surface for readers who already know bluntly: the latest honest reviews.",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/compare",
    file: "app/compare/page.tsx",
    title: "Compare products",
    group: "Discover",
    access: "public",
    purpose: "Side-by-side product comparison, chosen by id in the link (?ids=a,b,c) so it can be shared.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/reviews/[id]",
    file: "app/reviews/[id]/page.tsx",
    title: "Review",
    group: "Discover",
    access: "public",
    purpose: "One review in full: verdict, rating, pros and cons, photos, votes, comments, prices and where to buy.",
    figma: "Review page (4218:1196), More actions, Share to, Shop, Read more",
    inSitemap: false,
  },
  {
    path: "/sellers/[id]",
    file: "app/sellers/[id]/page.tsx",
    title: "Seller",
    group: "Discover",
    access: "public",
    purpose: "A store's page: rating summary, seller reviews and questions. Has the + action button.",
    figma: "Seller Page - Review (4218:2148), Seller Page - Questions (4295:1256), Action Menu (4417:751)",
    inSitemap: false,
  },
  {
    path: "/u/[id]",
    file: "app/u/[id]/page.tsx",
    title: "Public profile",
    group: "Discover",
    access: "public",
    purpose: "A reviewer's public profile: their stats and published reviews.",
    figma: "Profile Page - Reviews / Comments / Stats (5446:4328, 5446:6398, 5446:6532)",
    inSitemap: false,
  },

  // ----------------------------------------------------------------- Community
  {
    path: "/questions",
    file: "app/questions/page.tsx",
    title: "Questions",
    group: "Community",
    access: "public",
    purpose: "Every open question from the community, newest first, with a way to ask one.",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/questions/[id]",
    file: "app/questions/[id]/page.tsx",
    title: "Question",
    group: "Community",
    access: "public",
    purpose: "One question with its answers; answer it, or mark the best answer if it is yours.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/requests",
    file: "app/requests/page.tsx",
    title: "Requests",
    group: "Community",
    access: "public",
    purpose: "The request board (\"Bounty board\" in the menu): products people have asked to see reviewed.",
    figma: null,
    inSitemap: true,
  },

  // --------------------------------------------------------------------- Write
  {
    path: "/reviews/new",
    file: "app/reviews/new/page.tsx",
    title: "Write a review",
    group: "Write",
    access: "signed-in",
    purpose: "The seven-step product review composer, with proof of purchase, the price check and the done screen.",
    figma: "Reviewer Page - Step 1 to Step 7.1, All done (4550:8882), Let's talk money",
    inSitemap: false,
  },
  {
    path: "/sellers/rate",
    file: "app/sellers/rate/page.tsx",
    title: "Rate a seller",
    group: "Write",
    access: "signed-in",
    purpose: "Find or add a store, rate it on four dimensions, write it up; seller reviews go live on posting.",
    figma: "Seller Review - Step 1 to Step 3.3, All done (4652:12914)",
    inSitemap: false,
  },
  {
    path: "/questions/new",
    file: "app/questions/new/page.tsx",
    title: "Ask a question",
    group: "Write",
    access: "signed-in",
    purpose: "Choose who answers (buyers or the seller), pick the product, write the question.",
    figma: "Question Page - Buyer or Seller (4682:14203), Step 1 to Step 3 (4742:15979)",
    inSitemap: false,
  },
  {
    path: "/requests/new",
    file: "app/requests/new/page.tsx",
    title: "Post a request",
    group: "Write",
    access: "signed-in",
    purpose: "Ask for a product to be reviewed.",
    figma: null,
    inSitemap: false,
  },

  // ------------------------------------------------------------------- Sign in
  {
    path: "/welcome",
    file: "app/(auth)/welcome/page.tsx",
    title: "Welcome",
    group: "Sign in",
    access: "signed-out",
    purpose: "The entry screen: continue to sign up or log in.",
    figma: "Login & Signup (5357:2982)",
    inSitemap: false,
  },
  {
    path: "/login",
    file: "app/(auth)/login/page.tsx",
    title: "Log in",
    group: "Sign in",
    access: "signed-out",
    purpose: "Email one-time-code login; returns the reader to the page that sent them (?next=).",
    figma: "Login & Signup (5348:2789 family)",
    inSitemap: false,
  },
  {
    path: "/signup",
    file: "app/(auth)/signup/page.tsx",
    title: "Sign up",
    group: "Sign in",
    access: "signed-out",
    purpose: "Create an account with an emailed one-time code.",
    figma: "Login & Signup (5348:2789 family)",
    inSitemap: false,
  },
  {
    path: "/onboarding",
    file: "app/onboarding/page.tsx",
    title: "Set up your profile",
    group: "Sign in",
    access: "signed-in",
    purpose: "First-run setup: username, profile and interests.",
    figma: "Login & Signup onboarding states, InterestTile (6842:567), StepBar (6820:477)",
    inSitemap: false,
  },

  // ------------------------------------------------------------------- Account
  {
    path: "/profile/edit",
    file: "app/profile/edit/page.tsx",
    title: "Edit your profile",
    group: "Account",
    access: "signed-in",
    purpose: "Change your handle, display name, photo and interests in one form.",
    figma: "No frame — BUSINESS-REQUIRED (BUG-035). The file draws onboarding, which is a different job.",
    inSitemap: false,
  },
  {
    path: "/profile",
    file: "app/profile/page.tsx",
    title: "Your profile",
    group: "Account",
    access: "signed-in",
    purpose: "Your own profile: stats, verified reviews, comments, and sharing it.",
    figma: "Profile Page - Reviews / Comments / Stats (5446:4328, 5446:6398, 5446:6532)",
    inSitemap: false,
  },
  {
    path: "/notifications",
    file: "app/notifications/page.tsx",
    title: "Notifications",
    group: "Account",
    access: "signed-in",
    purpose: "Your account's notifications.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/contracts",
    file: "app/contracts/page.tsx",
    title: "Contracts",
    group: "Account",
    access: "signed-in",
    purpose: "Your review contracts and where each stands: active, expired or bought out.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/sellers/[id]/dashboard",
    file: "app/sellers/[id]/dashboard/page.tsx",
    title: "Store dashboard",
    group: "Account",
    access: "store-owner",
    purpose: "Review monitoring for a store's approved owner; anyone else is told how to claim the store.",
    figma: null,
    inSitemap: false,
  },

  // ------------------------------------------------------------------ Earnings
  {
    path: "/dashboard",
    file: "app/dashboard/page.tsx",
    title: "Earnings",
    group: "Earnings",
    access: "signed-in",
    purpose: "The reviewer dashboard: earnings, balance and recent performance.",
    figma: "Reviewer Dashboard (5572:7130, 6006:918)",
    inSitemap: false,
  },
  {
    path: "/dashboard/history",
    file: "app/dashboard/history/page.tsx",
    title: "Earnings history",
    group: "Earnings",
    access: "signed-in",
    purpose: "All-time income and every commission behind it.",
    figma: "Reviewer Dashboard - History (5762:472, 6158:1240)",
    inSitemap: false,
  },
  {
    path: "/dashboard/reviews",
    file: "app/dashboard/reviews/page.tsx",
    title: "Your reviews",
    group: "Earnings",
    access: "signed-in",
    purpose: "Your reviews and how each is doing.",
    figma: "Reviewer Dashboard - Reviews (6159:1510)",
    inSitemap: false,
  },
  {
    path: "/dashboard/transfer",
    file: "app/dashboard/transfer/page.tsx",
    title: "Transfer",
    group: "Earnings",
    access: "signed-in",
    purpose: "Your balance, how far it is from the withdrawal threshold, the payout account and the withdrawal request.",
    figma: "Reviewer Dashboard - Transfer (5762:332)",
    inSitemap: false,
  },
  {
    path: "/dashboard/insights",
    file: "app/dashboard/insights/page.tsx",
    title: "Insights",
    group: "Earnings",
    access: "signed-in",
    purpose: "Your review streak and activity charts.",
    figma: "Insights (5762:752)",
    inSitemap: false,
  },

  // ------------------------------------------------------------------- Company
  {
    path: "/about",
    file: "app/about/page.tsx",
    title: "About",
    group: "Company",
    access: "public",
    purpose: "What bluntly is: reviews by real buyers, checked by moderators, never paid for by brands.",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/how-it-works",
    file: "app/how-it-works/page.tsx",
    title: "How it works",
    group: "Company",
    access: "public",
    purpose: "How a real purchase becomes a moderated review that pays the person who wrote it.",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/membership",
    file: "app/membership/page.tsx",
    title: "Membership tiers",
    group: "Company",
    access: "public",
    purpose: "Special, Founding and Standard tiers: revenue share and payout priority. Tiers are earned, never bought.",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/faqs",
    file: "app/faqs/page.tsx",
    title: "FAQs",
    group: "Company",
    access: "public",
    purpose: "Common questions: earning, verification, payouts and getting started.",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/articles",
    file: "app/articles/page.tsx",
    title: "Articles",
    group: "Company",
    access: "public",
    purpose: "Guides and explainers from the bluntly team (coming soon).",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/contact",
    file: "app/contact/page.tsx",
    title: "Contact",
    group: "Company",
    access: "public",
    purpose: "Reach the team about support, moderation, press, partnerships or feedback.",
    figma: null,
    inSitemap: true,
  },

  // --------------------------------------------------------------------- Legal
  {
    path: "/guidelines",
    file: "app/guidelines/page.tsx",
    title: "Community guidelines",
    group: "Legal",
    access: "public",
    purpose: "The rules that keep reviews real: genuine experience, independence, original words and photos.",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/legal",
    file: "app/legal/page.tsx",
    title: "Legal & disclosures",
    group: "Legal",
    access: "public",
    purpose: "How bluntly makes money, the affiliate disclosure, and links to the policies.",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/terms",
    file: "app/terms/page.tsx",
    title: "Terms & Conditions",
    group: "Legal",
    access: "public",
    purpose: "The terms for accounts, content, acceptable use, affiliate earnings and payouts.",
    figma: null,
    inSitemap: true,
  },
  {
    path: "/privacy",
    file: "app/privacy/page.tsx",
    title: "Privacy Policy",
    group: "Legal",
    access: "public",
    purpose: "What bluntly.ph collects, why, and the choices you have.",
    figma: null,
    inSitemap: true,
  },

  // ---------------------------------------------------------------- Moderation
  {
    path: "/moderate",
    file: "app/moderate/page.tsx",
    title: "Overview",
    group: "Moderation",
    access: "moderator",
    purpose: "The moderator landing: what is urgent, summary figures and recent activity.",
    figma: "Overview (5017:1738) in the Admin/Sidebar shell (5017:2225)",
    inSitemap: false,
  },
  {
    path: "/moderate/review-queue",
    file: "app/moderate/review-queue/page.tsx",
    title: "Review queue",
    group: "Moderation",
    access: "moderator",
    purpose: "Reviews waiting for a moderator, with the Q&A and Support tabs; filtered and paged on the server.",
    figma: "Admin Page - Review Queue (6922:837), the file's one desktop frame",
    inSitemap: false,
  },
  {
    path: "/moderate/products",
    file: "app/moderate/products/page.tsx",
    title: "Products",
    group: "Moderation",
    access: "moderator",
    purpose: "The product catalogue, read-only, with how much has been written about each.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/moderate/prices",
    file: "app/moderate/prices/page.tsx",
    title: "Prices",
    group: "Moderation",
    access: "moderator",
    purpose: "Community price reports waiting for approval before they reach a product page.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/moderate/sellers",
    file: "app/moderate/sellers/page.tsx",
    title: "Sellers",
    group: "Moderation",
    access: "moderator",
    purpose: "Seller claims waiting for a moderator, with the claimant's evidence beside the store.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/moderate/reviewers",
    file: "app/moderate/reviewers/page.tsx",
    title: "Reviewers",
    group: "Moderation",
    access: "moderator",
    purpose: "The platform's reviewers: trust stage, reputation, published reviews and payouts.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/moderate/users",
    file: "app/moderate/users/page.tsx",
    title: "User management",
    group: "Moderation",
    access: "moderator",
    purpose: "Accounts, their roles and suspensions.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/moderate/affiliate-links",
    file: "app/moderate/affiliate-links/page.tsx",
    title: "Affiliate links",
    group: "Moderation",
    access: "moderator",
    purpose: "The affiliate ledger: what the marketplace reported and what our own ledger settled.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/moderate/honesty-fund",
    file: "app/moderate/honesty-fund/page.tsx",
    title: "Honesty Fund",
    group: "Moderation",
    access: "moderator",
    purpose: "The Honesty Fund pool for the current cycle. Distribution is scheduled, not a button.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/moderate/analytics",
    file: "app/moderate/analytics/page.tsx",
    title: "Where requests come from",
    group: "Moderation",
    access: "moderator",
    purpose: "Traffic geography: the globe and the country breakdown.",
    figma: null,
    inSitemap: false,
  },
  {
    path: "/moderate/activity",
    file: "app/moderate/activity/page.tsx",
    title: "Activity log",
    group: "Moderation",
    access: "moderator",
    purpose: "The full moderation audit log.",
    figma: null,
    inSitemap: false,
  },
];

export type SystemRoute = {
  path: string;
  /** "app": a route handler in this repo's app/; "backend": rewritten to the API service (vercel.json). */
  source: "app" | "backend" | "metadata";
  purpose: string;
};

/** Addresses that are not pages. Listed so the inventory has no unknown routes. */
export const SYSTEM_ROUTES: SystemRoute[] = [
  { path: "/api/bff/[...path]", source: "app", purpose: "The browser's proxy to the API, carrying the session cookie." },
  { path: "/api/telemetry", source: "app", purpose: "Reading telemetry from review pages." },
  { path: "/api/v1/*", source: "backend", purpose: "The FastAPI service." },
  { path: "/r/*", source: "backend", purpose: "Attributed affiliate redirects to the marketplace." },
  { path: "/health", source: "backend", purpose: "The API's health check." },
  { path: "/sitemap.xml", source: "metadata", purpose: "This map's public pages, for search engines (app/sitemap.ts)." },
  { path: "/robots.txt", source: "metadata", purpose: "Crawler rules and the sitemap's address (app/robots.ts)." },
  { path: "/icon.svg", source: "metadata", purpose: "The site icon (app/icon.svg)." },
];

/** The paths /sitemap.xml lists. */
export function sitemapPaths(): string[] {
  return SITE_ROUTES.filter((r) => r.inSitemap).map((r) => r.path);
}

const ACCESS_LABEL: Record<Access, string> = {
  public: "Public",
  "signed-out": "Signed-out only",
  "signed-in": "Signed in",
  moderator: "Moderator",
  "store-owner": "Store owner",
};

const GROUPS: Group[] = [
  "Discover",
  "Community",
  "Write",
  "Sign in",
  "Account",
  "Earnings",
  "Company",
  "Legal",
  "Moderation",
];

const cell = (text: string) => text.replace(/\|/g, "\\|");

/** docs/SITEMAP.md, generated from this file by `npm run sitemap:docs`. */
export function siteMapMarkdown(): string {
  const withFigma = SITE_ROUTES.filter((r) => r.figma !== null).length;
  const lines: string[] = [
    "# bluntly.ph site map",
    "",
    "<!-- Generated from lib/site-map.ts by `npm run sitemap:docs`. Edit that file, not this one. -->",
    "",
    `${SITE_ROUTES.length} pages: ${withFigma} built to Figma frames, ${SITE_ROUTES.length - withFigma} with no frame in the file`,
    "(product and business pages kept from the PRD, styled in the Figma system's language).",
    `${sitemapPaths().length} public pages are listed in ${SITE_URL}/sitemap.xml.`,
    "",
    "Access: **Public** anyone; **Signed-out only** a signed-in reader is sent home; **Signed in** a",
    "signed-out visitor is sent to /login and brought back; **Moderator** signed in with the moderator",
    "role; **Store owner** signed in, and only the store's approved owner sees its figures.",
    "",
  ];
  for (const group of GROUPS) {
    const routes = SITE_ROUTES.filter((r) => r.group === group);
    if (routes.length === 0) continue;
    lines.push(`## ${group}`, "", "| Page | Path | Access | What it is for | Figma | sitemap.xml |", "| --- | --- | --- | --- | --- | --- |");
    for (const r of routes) {
      lines.push(
        `| ${cell(r.title)} | \`${r.path}\` | ${ACCESS_LABEL[r.access]} | ${cell(r.purpose)} | ${
          r.figma ? cell(r.figma) : "No frame"
        } | ${r.inSitemap ? "Yes" : "No"} |`,
      );
    }
    lines.push("");
  }
  lines.push("## Not pages", "", "| Path | Served by | What it is for |", "| --- | --- | --- |");
  for (const r of SYSTEM_ROUTES) {
    const by = r.source === "app" ? "Next route handler" : r.source === "backend" ? "API service" : "Next metadata";
    lines.push(`| \`${r.path}\` | ${by} | ${cell(r.purpose)} |`);
  }
  lines.push("");
  return lines.join("\n");
}
