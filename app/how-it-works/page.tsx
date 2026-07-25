import type { Metadata } from "next";
import Link from "next/link";

import { Article, type Block } from "@/components/site/Article";
import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "How bluntly works — bluntly",
  description:
    "How a real purchase becomes an honest, moderated review that pays the person who wrote it — with no sponsorships, ever.",
};

const BLOCKS: Block[] = [
  {
    type: "lead",
    text: "bluntly turns real purchases into honest reviews that actually pay the people who write them — no sponsorships, no paid placements, no bias. Ever.",
  },
  { type: "h2", text: "Why another review site?" },
  {
    type: "p",
    text: "Most product reviews online are bought. Sponsored five-stars, undisclosed freebies, and copy-paste praise make it hard to tell what is genuinely worth your money — and here, a bad buy stings.",
  },
  {
    type: "p",
    text: "bluntly flips the incentive. Reviewers earn when their honest write-up helps you decide, not when they flatter a brand — and a moderator checks every review before it goes live.",
  },
  { type: "h2", text: "From a purchase to a published review" },
  {
    type: "ol",
    items: [
      "You bought something on Shopee, Lazada, TikTok Shop, or Amazon. Paste the purchase link.",
      "Write it straight. A guided form walks you through the experience, a clear verdict (Worth it, It depends, or Hard pass), who it is and is not for, the pros and cons, and a star rating.",
      "A moderator verifies it is genuine and attaches an affiliate link.",
      "It publishes. When a reader taps “Buy it here” and buys, you earn a commission.",
    ],
  },
  { type: "h2", text: "Where the money goes" },
  { type: "p", text: "Every commission a review earns is split three ways:" },
  {
    type: "ul",
    items: [
      "40% keeps bluntly running — moderation, hosting, and payouts.",
      "30% goes to the reviewer who did the work.",
      "30% goes to the Honesty Fund.",
    ],
  },
  {
    type: "p",
    text: "The Honesty Fund is the point. It rewards honest reviewers even when the verdict is “Hard pass,” so there is never a reason to shill. A negative review that saves you money is worth just as much here as a glowing one.",
  },
  { type: "h2", text: "Trust you can see" },
  {
    type: "p",
    text: "Reviewers move through six trust stages as they build a track record of genuine, consistent reviews. Verified buyers, first responders, and best answers are marked — so you always know who you are reading.",
  },
  { type: "h2", text: "Getting paid" },
  {
    type: "p",
    text: "Earnings collect in your wallet as your reviews drive sales. Once your balance reaches ₱300, you can withdraw it to PayPal from your dashboard.",
  },
];

export default function HowItWorksPage() {
  return (
    <PageShell>
      <Article title="How bluntly works" blocks={BLOCKS}>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/reviews/new"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-6 text-[14px] font-semibold text-white shadow-[var(--shadow-card)] transition-colors hover:bg-[var(--accent-primary-strong)]"
          >
            Write your first review
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
