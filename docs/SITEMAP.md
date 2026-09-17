# bluntly.ph site map

<!-- Generated from lib/site-map.ts by `npm run sitemap:docs`. Edit that file, not this one. -->

50 pages: 21 built to Figma frames, 29 with no frame in the file
(product and business pages kept from the PRD, styled in the Figma system's language).
16 public pages are listed in https://www.bluntly.ph/sitemap.xml.

Access: **Public** anyone; **Signed-out only** a signed-in reader is sent home; **Signed in** a
signed-out visitor is sent to /login and brought back; **Moderator** signed in with the moderator
role; **Store owner** signed in, and only the store's approved owner sees its figures.

## Discover

| Page | Path | Access | What it is for | Figma | sitemap.xml |
| --- | --- | --- | --- | --- | --- |
| Landing | `/` | Public | The front door: what bluntly is, the ask-anything search, a featured review and the trust story. | Mobile Landing Page (1902:1504) | Yes |
| Search | `/search` | Public | Search reviews, questions and sellers in tabs, with filters, sort and recent searches. Has the + action button. | Mobile Search Page for Buyers / Reviewers / Sellers (3481:1776, 3481:1894, 3954:650), All filters, Sort | Yes |
| Categories | `/categories` | Public | Browse every product category; a category opens search filtered to it. | Categories (2355:939), Subcategory (2355:2267) | Yes |
| Feed | `/feed` | Public | The browsing surface for readers who already know bluntly: the latest honest reviews. | No frame | Yes |
| Compare products | `/compare` | Public | Side-by-side product comparison, chosen by id in the link (?ids=a,b,c) so it can be shared. | No frame | No |
| Review | `/reviews/[id]` | Public | One review in full: verdict, rating, pros and cons, photos, votes, comments, prices and where to buy. | Review page (4218:1196), More actions, Share to, Shop, Read more | No |
| Seller | `/sellers/[id]` | Public | A store's page: rating summary, seller reviews and questions. Has the + action button. | Seller Page - Review (4218:2148), Seller Page - Questions (4295:1256), Action Menu (4417:751) | No |
| Public profile | `/u/[id]` | Public | A reviewer's public profile: their stats and published reviews. | Profile Page - Reviews / Comments / Stats (5446:4328, 5446:6398, 5446:6532) | No |

## Community

| Page | Path | Access | What it is for | Figma | sitemap.xml |
| --- | --- | --- | --- | --- | --- |
| Questions | `/questions` | Public | Every open question from the community, newest first, with a way to ask one. | No frame | Yes |
| Question | `/questions/[id]` | Public | One question with its answers; answer it, or mark the best answer if it is yours. | No frame | No |
| Requests | `/requests` | Public | The request board ("Bounty board" in the menu): products people have asked to see reviewed. | No frame | Yes |

## Write

| Page | Path | Access | What it is for | Figma | sitemap.xml |
| --- | --- | --- | --- | --- | --- |
| Write a review | `/reviews/new` | Signed in | The seven-step product review composer, with proof of purchase, the price check and the done screen. | Reviewer Page - Step 1 to Step 7.1, All done (4550:8882), Let's talk money | No |
| Rate a seller | `/sellers/rate` | Signed in | Find or add a store, rate it on four dimensions, write it up; seller reviews go live on posting. | Seller Review - Step 1 to Step 3.3, All done (4652:12914) | No |
| Ask a question | `/questions/new` | Signed in | Choose who answers (buyers or the seller), pick the product, write the question. | Question Page - Buyer or Seller (4682:14203), Step 1 to Step 3 (4742:15979) | No |
| Post a request | `/requests/new` | Signed in | Ask for a product to be reviewed. | No frame | No |

## Sign in

| Page | Path | Access | What it is for | Figma | sitemap.xml |
| --- | --- | --- | --- | --- | --- |
| Welcome | `/welcome` | Signed-out only | The entry screen: continue to sign up or log in. | Login & Signup (5357:2982) | No |
| Log in | `/login` | Signed-out only | Email one-time-code login; returns the reader to the page that sent them (?next=). | Login & Signup (5348:2789 family) | No |
| Sign up | `/signup` | Signed-out only | Create an account with an emailed one-time code. | Login & Signup (5348:2789 family) | No |
| Set up your profile | `/onboarding` | Signed in | First-run setup: username, profile and interests. | Login & Signup onboarding states, InterestTile (6842:567), StepBar (6820:477) | No |

## Account

| Page | Path | Access | What it is for | Figma | sitemap.xml |
| --- | --- | --- | --- | --- | --- |
| Edit your profile | `/profile/edit` | Signed in | Change your handle, display name, photo and interests in one form. | No frame — BUSINESS-REQUIRED (BUG-035). The file draws onboarding, which is a different job. | No |
| Your profile | `/profile` | Signed in | Your own profile: stats, verified reviews, comments, and sharing it. | Profile Page - Reviews / Comments / Stats (5446:4328, 5446:6398, 5446:6532) | No |
| Notifications | `/notifications` | Signed in | Your account's notifications. | No frame | No |
| Contracts | `/contracts` | Signed in | Your review contracts and where each stands: active, expired or bought out. | No frame | No |
| Store dashboard | `/sellers/[id]/dashboard` | Store owner | Review monitoring for a store's approved owner; anyone else is told how to claim the store. | No frame | No |

## Earnings

| Page | Path | Access | What it is for | Figma | sitemap.xml |
| --- | --- | --- | --- | --- | --- |
| Earnings | `/dashboard` | Signed in | The reviewer dashboard: earnings, balance and recent performance. | Reviewer Dashboard (5572:7130, 6006:918) | No |
| Earnings history | `/dashboard/history` | Signed in | All-time income and every commission behind it. | Reviewer Dashboard - History (5762:472, 6158:1240) | No |
| Your reviews | `/dashboard/reviews` | Signed in | Your reviews and how each is doing. | Reviewer Dashboard - Reviews (6159:1510) | No |
| Transfer | `/dashboard/transfer` | Signed in | Your balance, how far it is from the withdrawal threshold, the payout account and the withdrawal request. | Reviewer Dashboard - Transfer (5762:332) | No |
| Insights | `/dashboard/insights` | Signed in | Views on your reviews over a chosen period, and your contribution streak. | No frame | No |

## Company

| Page | Path | Access | What it is for | Figma | sitemap.xml |
| --- | --- | --- | --- | --- | --- |
| About | `/about` | Public | What bluntly is: reviews by real buyers, checked by moderators, never paid for by brands. | No frame | Yes |
| How it works | `/how-it-works` | Public | How a real purchase becomes a moderated review that pays the person who wrote it. | No frame | Yes |
| Membership tiers | `/membership` | Public | Special, Founding and Standard tiers: revenue share and payout priority. Tiers are earned, never bought. | No frame | Yes |
| FAQs | `/faqs` | Public | Common questions: earning, verification, payouts and getting started. | No frame | Yes |
| Articles | `/articles` | Public | Guides and explainers from the bluntly team (coming soon). | No frame | Yes |
| Contact | `/contact` | Public | Reach the team about support, moderation, press, partnerships or feedback. | No frame | Yes |

## Legal

| Page | Path | Access | What it is for | Figma | sitemap.xml |
| --- | --- | --- | --- | --- | --- |
| Community guidelines | `/guidelines` | Public | The rules that keep reviews real: genuine experience, independence, original words and photos. | No frame | Yes |
| Legal & disclosures | `/legal` | Public | How bluntly makes money, the affiliate disclosure, and links to the policies. | No frame | Yes |
| Terms & Conditions | `/terms` | Public | The terms for accounts, content, acceptable use, affiliate earnings and payouts. | No frame | Yes |
| Privacy Policy | `/privacy` | Public | What bluntly.ph collects, why, and the choices you have. | No frame | Yes |

## Moderation

| Page | Path | Access | What it is for | Figma | sitemap.xml |
| --- | --- | --- | --- | --- | --- |
| Overview | `/moderate` | Moderator | The moderator landing: what is urgent, summary figures and recent activity. | Admin/Sidebar shell (5017:2225) | No |
| Review queue | `/moderate/review-queue` | Moderator | Reviews waiting for a moderator, with the Q&A and Support tabs; filtered and paged on the server. | Admin Page - Review Queue (6922:837), the file's one desktop frame | No |
| Products | `/moderate/products` | Moderator | The product catalogue, read-only, with how much has been written about each. | No frame | No |
| Prices | `/moderate/prices` | Moderator | Community price reports waiting for approval before they reach a product page. | No frame | No |
| Sellers | `/moderate/sellers` | Moderator | Seller claims waiting for a moderator, with the claimant's evidence beside the store. | No frame | No |
| Reviewers | `/moderate/reviewers` | Moderator | The platform's reviewers: trust stage, reputation, published reviews and payouts. | No frame | No |
| User management | `/moderate/users` | Moderator | Accounts, their roles and suspensions. | No frame | No |
| Affiliate links | `/moderate/affiliate-links` | Moderator | The affiliate ledger: what the marketplace reported and what our own ledger settled. | No frame | No |
| Honesty Fund | `/moderate/honesty-fund` | Moderator | The Honesty Fund pool for the current cycle. Distribution is scheduled, not a button. | No frame | No |
| Where requests come from | `/moderate/analytics` | Moderator | Traffic geography: the globe and the country breakdown. | No frame | No |
| Activity log | `/moderate/activity` | Moderator | The full moderation audit log. | No frame | No |

## Not pages

| Path | Served by | What it is for |
| --- | --- | --- |
| `/api/bff/[...path]` | Next route handler | The browser's proxy to the API, carrying the session cookie. |
| `/api/telemetry` | Next route handler | Reading telemetry from review pages. |
| `/api/v1/*` | API service | The FastAPI service. |
| `/r/*` | API service | Attributed affiliate redirects to the marketplace. |
| `/health` | API service | The API's health check. |
| `/sitemap.xml` | Next metadata | This map's public pages, for search engines (app/sitemap.ts). |
| `/robots.txt` | Next metadata | Crawler rules and the sitemap's address (app/robots.ts). |
| `/icon.svg` | Next metadata | The site icon (app/icon.svg). |
