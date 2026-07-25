import type { Metadata } from "next";

import { Article, type Block } from "@/components/site/Article";
import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "Terms & Conditions — bluntly",
  description:
    "The terms that govern your use of bluntly.ph — accounts, content, acceptable use, affiliate earnings, and payouts.",
};

const BLOCKS: Block[] = [
  {
    type: "lead",
    text: "These terms govern your use of bluntly.ph. By using the platform, you agree to them.",
  },
  { type: "h2", text: "Eligibility and accounts" },
  {
    type: "p",
    text: "You must be at least 13 and able to form a binding agreement. You are responsible for activity on your account and for keeping your sign-in secure.",
  },
  { type: "h2", text: "Your content" },
  {
    type: "p",
    text: "You keep ownership of the reviews, photos, questions, and answers you post. You grant bluntly a non-exclusive, worldwide, royalty-free license to host, display, and promote that content on and off the platform. You are responsible for what you post and confirm it is your own honest experience and work.",
  },
  { type: "h2", text: "Acceptable use" },
  {
    type: "p",
    text: "You agree to follow our Community Guidelines. In particular: no fake, sponsored, plagiarized, or manipulated reviews, and no attempts to game earnings, votes, or trust standing.",
  },
  { type: "h2", text: "Reviews and moderation" },
  {
    type: "p",
    text: "Reviews are submitted for moderation and may be published, edited for policy, or rejected at our discretion. Reviews reflect the personal opinions of their authors, not bluntly.",
  },
  { type: "h2", text: "Affiliate earnings and payouts" },
  {
    type: "ul",
    items: [
      "Published reviews may earn affiliate commissions when they drive a sale through their attached link.",
      "Reviewer earnings accrue to your wallet and become withdrawable via PayPal once your balance reaches ₱300.",
      "We may withhold, reverse, or forfeit earnings tied to fraud, guideline violations, or reversed or invalid affiliate transactions.",
    ],
  },
  { type: "h2", text: "Third-party sellers" },
  {
    type: "p",
    text: "Purchases happen on third-party platforms such as Shopee, Lazada, TikTok Shop, and Amazon, under their own terms. bluntly is not the seller and is not responsible for those transactions, products, or fulfillment.",
  },
  { type: "h2", text: "Disclaimers" },
  {
    type: "p",
    text: "bluntly is provided “as is,” without warranties of any kind. Reviews are opinions, not professional advice.",
  },
  { type: "h2", text: "Limitation of liability" },
  {
    type: "p",
    text: "To the maximum extent permitted by law, bluntly is not liable for indirect, incidental, or consequential damages arising from your use of the platform.",
  },
  { type: "h2", text: "Suspension and termination" },
  {
    type: "p",
    text: "We may suspend or close accounts that violate these terms or our Community Guidelines.",
  },
  { type: "h2", text: "Governing law" },
  {
    type: "p",
    text: "These terms are governed by the laws of the Republic of the Philippines.",
  },
  { type: "h2", text: "Changes and contact" },
  {
    type: "node",
    node: (
      <p>
        We may update these terms; continued use means you accept the changes.
        Questions? Email <a href="mailto:bluntly.ph@gmail.com">bluntly.ph@gmail.com</a>.
      </p>
    ),
  },
];

export default function TermsPage() {
  return (
    <PageShell>
      <Article title="Terms & Conditions" meta="Last updated July 2026" blocks={BLOCKS} />
    </PageShell>
  );
}
