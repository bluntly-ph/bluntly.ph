import type { Metadata } from "next";
import Link from "next/link";

import { Article, type Block } from "@/components/site/Article";
import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "FAQs — bluntly",
  description:
    "Answers to common questions about bluntly: how reviewers earn, how reviews are verified, payouts, and getting started.",
};

const FAQS: { q: string; a: string }[] = [
  {
    q: "Is bluntly free?",
    a: "Yes. Reading reviews and asking questions is completely free. Writing reviews is free too — and it can earn you money.",
  },
  {
    q: "How do reviewers earn?",
    a: "When your published review drives a sale through its “Buy it here” link, it earns an affiliate commission. Reviewers receive a share of that, plus rewards from the Honesty Fund.",
  },
  {
    q: "Do I have to write only positive reviews to earn?",
    a: "No — and that is the whole idea. The Honesty Fund pays honest reviewers regardless of their verdict, so a well-argued “Hard pass” is just as valuable as a rave.",
  },
  {
    q: "How are reviews verified?",
    a: "Every review begins with a real purchase link, and a moderator checks each submission before it goes live. Reviewers also build standing through six trust stages as their track record grows.",
  },
  {
    q: "When and how do I get paid?",
    a: "Earnings collect in your wallet. Once your balance reaches ₱300, you can withdraw it to PayPal from your dashboard.",
  },
  {
    q: "What can I review?",
    a: "Anything you actually bought on Shopee, Lazada, TikTok Shop, or Amazon. Paste the purchase link to get started.",
  },
  {
    q: "Are the “Buy it here” links safe?",
    a: "Yes. They route through bluntly to the seller you already know. bluntly may earn a commission at no extra cost to you — that is what funds honest reviews and reviewer payouts.",
  },
  {
    q: "Can I ask a question about a product?",
    a: "Yes. Use Q&A to ask owners and verified buyers directly — helpful answers earn badges and recognition.",
  },
  {
    q: "How do I start?",
    a: "Sign in with your email, paste a purchase link, and write your first review. A moderator takes it from there.",
  },
];

const BLOCKS: Block[] = [
  {
    type: "lead",
    text: "The short answers. Still stuck? Reach us any time — the contact page has the details.",
  },
  ...FAQS.flatMap(
    (f): Block[] => [
      { type: "h3", text: f.q },
      { type: "p", text: f.a },
    ],
  ),
];

export default function FaqsPage() {
  return (
    <PageShell>
      <Article title="Frequently asked questions" blocks={BLOCKS}>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/how-it-works"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-6 text-[14px] font-semibold text-white shadow-[var(--shadow-card)] transition-colors hover:bg-[var(--accent-primary-strong)]"
          >
            See how it works
          </Link>
          <Link
            href="/contact"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-6 text-[14px] font-semibold text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] transition-colors hover:text-[var(--accent-primary)]"
          >
            Contact us
          </Link>
        </div>
      </Article>
    </PageShell>
  );
}
