import type { Metadata } from "next";
import Link from "next/link";

import { Article, type Block } from "@/components/site/Article";
import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "Legal & disclosures — bluntly",
  description:
    "How bluntly makes money, our affiliate disclosure and independence, and where to find our policies.",
};

const BLOCKS: Block[] = [
  {
    type: "lead",
    text: "The short version of how bluntly makes money, and where to find our policies.",
  },
  { type: "h2", text: "Affiliate disclosure" },
  {
    type: "p",
    text: "bluntly earns affiliate commissions when readers buy through the “Buy it here” links attached to reviews, at no extra cost to you. This never changes a reviewer's verdict: the Honesty Fund pays honest reviewers whether their review is positive or negative, so there is no incentive to recommend a product just to earn.",
  },
  { type: "h2", text: "Independence" },
  {
    type: "p",
    text: "We do not accept payment from brands to publish, alter, or rank reviews. Sponsored and incentivized reviews are not allowed.",
  },
  { type: "h2", text: "Our policies" },
  {
    type: "node",
    node: (
      <ul>
        <li>
          <Link href="/privacy">Privacy Policy</Link>
        </li>
        <li>
          <Link href="/terms">{"Terms & Conditions"}</Link>
        </li>
        <li>
          <Link href="/guidelines">Community Guidelines</Link>
        </li>
      </ul>
    ),
  },
  { type: "h2", text: "Trademarks" },
  {
    type: "p",
    text: "Shopee, Lazada, TikTok Shop, Amazon, PayPal, and other names are trademarks of their respective owners, used here for identification only. bluntly is not affiliated with or endorsed by them.",
  },
  { type: "h2", text: "Contact" },
  {
    type: "node",
    node: (
      <p>
        Questions about anything on this page? Email{" "}
        <a href="mailto:bluntly.ph@gmail.com">bluntly.ph@gmail.com</a>.
      </p>
    ),
  },
];

export default function LegalPage() {
  return (
    <PageShell>
      <Article title="Legal & disclosures" blocks={BLOCKS} />
    </PageShell>
  );
}
