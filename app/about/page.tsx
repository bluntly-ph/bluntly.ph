import type { Metadata } from "next";
import Link from "next/link";

import { Article, type Block } from "@/components/site/Article";
import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "About bluntly — bluntly",
  description:
    "bluntly is an honest-review platform for Filipino shoppers: reviews written by real buyers, checked by moderators, and never paid for by brands.",
};

const BLOCKS: Block[] = [
  {
    type: "lead",
    text: "bluntly is an honest-review platform for Filipino shoppers. The reviews are written by people who actually bought the product, checked by moderators, and never paid for by brands.",
  },
  { type: "h2", text: "The problem" },
  {
    type: "p",
    text: "Online reviews stopped being trustworthy. Sponsored posts, incentivized ratings, and undisclosed freebies drowned out real experience. For everyday shoppers deciding whether something is worth their hard-earned money, that is more than an annoyance — it is expensive.",
  },
  { type: "h2", text: "What we do differently" },
  {
    type: "ul",
    items: [
      "Every review starts from a real purchase link on Shopee, Lazada, TikTok Shop, or Amazon.",
      "A moderator reviews each submission before it is published.",
      "Reviewers earn from affiliate commissions — and the Honesty Fund pays them for honesty, not for praise, so negative reviews are just as valuable.",
      "No sponsorships, no paid placements, and no brand influence on verdicts.",
    ],
  },
  { type: "h2", text: "Who it is for" },
  {
    type: "p",
    text: "Readers who want a straight answer before they buy, and reviewers who want their honest take to be worth something. Reading is always free; writing can pay.",
  },
  { type: "h2", text: "Our promise" },
  {
    type: "p",
    text: "Honest reviews. Real payouts. No sponsorships. No bias. Ever.",
  },
];

export default function AboutPage() {
  return (
    <PageShell>
      <Article title="About bluntly" blocks={BLOCKS}>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/how-it-works"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-6 text-[14px] font-semibold text-white shadow-[var(--shadow-card)] transition-colors hover:bg-[var(--accent-primary-strong)]"
          >
            See how it works
          </Link>
          <Link
            href="/search"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-6 text-[14px] font-semibold text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] transition-colors hover:text-[var(--accent-primary)]"
          >
            Browse reviews
          </Link>
        </div>
      </Article>
    </PageShell>
  );
}
