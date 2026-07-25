import type { Metadata } from "next";

import { Article, type Block } from "@/components/site/Article";
import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "Privacy Policy — bluntly",
  description:
    "What bluntly.ph collects, why, and the choices you have — including your rights under the Philippine Data Privacy Act.",
};

const MAIL = <a href="mailto:bluntly.ph@gmail.com">bluntly.ph@gmail.com</a>;

const BLOCKS: Block[] = [
  {
    type: "lead",
    text: "This policy explains what bluntly.ph collects, why, and the choices you have. We keep it short and specific.",
  },
  { type: "h2", text: "Who we are" },
  {
    type: "node",
    node: <p>bluntly.ph (&ldquo;bluntly,&rdquo; &ldquo;we&rdquo;) operates this honest-review platform. For any privacy question, email {MAIL}.</p>,
  },
  { type: "h2", text: "What we collect" },
  {
    type: "ul",
    items: [
      "Account details — your email address and the profile information you provide (username, display name, avatar).",
      "Content you create — reviews, ratings, questions, answers, votes, and the purchase links you submit.",
      "Payout details — the PayPal address you use to withdraw earnings.",
      "Usage data — basic device, log, and analytics information needed to run and secure the service.",
    ],
  },
  { type: "h2", text: "How we use it" },
  {
    type: "ul",
    items: [
      "To operate the platform — publish your reviews, run Q&A, and show relevant content.",
      "To verify reviews and enforce our Community Guidelines.",
      "To calculate and send reviewer payouts.",
      "To secure the service and prevent fraud and abuse.",
    ],
  },
  { type: "h2", text: "Affiliate links and analytics" },
  {
    type: "p",
    text: "When you tap “Buy it here,” you are routed to a third-party seller through an affiliate link. Those sellers and affiliate networks receive the click and may set their own cookies under their own policies. We use limited analytics to understand what is useful.",
  },
  { type: "h2", text: "Sharing" },
  {
    type: "p",
    text: "We do not sell your personal information. We share data only with service providers that help us run bluntly — such as email delivery, hosting, and payout processing — and where required by law.",
  },
  { type: "h2", text: "Your choices and rights" },
  {
    type: "node",
    node: (
      <p>
        You can access, correct, or delete your account information, and request a
        copy of your data, by emailing {MAIL}. Consistent with the Philippine Data
        Privacy Act of 2012, we honor valid requests to exercise your rights.
      </p>
    ),
  },
  { type: "h2", text: "Data retention and security" },
  {
    type: "p",
    text: "We keep your information for as long as your account is active or as needed to provide the service, meet legal obligations, and resolve disputes. We use reasonable safeguards to protect it, though no online service can promise perfect security.",
  },
  { type: "h2", text: "Children" },
  {
    type: "p",
    text: "bluntly is not intended for anyone under 13, and we do not knowingly collect their information.",
  },
  { type: "h2", text: "Changes" },
  {
    type: "p",
    text: "We may update this policy; material changes will be reflected by the date above.",
  },
];

export default function PrivacyPage() {
  return (
    <PageShell>
      <Article title="Privacy Policy" meta="Last updated July 2026" blocks={BLOCKS} />
    </PageShell>
  );
}
