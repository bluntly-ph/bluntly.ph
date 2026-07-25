import type { Metadata } from "next";

import { Article, type Block } from "@/components/site/Article";
import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "Community Guidelines — bluntly",
  description:
    "The rules that keep bluntly reviews real: genuine experience, independence, original words and photos, and respect.",
};

const BLOCKS: Block[] = [
  {
    type: "lead",
    text: "bluntly only works if the reviews are real. These are the rules everyone agrees to by posting.",
  },
  { type: "h2", text: "Write from real experience" },
  {
    type: "p",
    text: "Only review products you actually bought and used, starting from a genuine purchase link. No hypotheticals, and no reviewing on someone else's behalf.",
  },
  { type: "h2", text: "Stay independent" },
  {
    type: "p",
    text: "No sponsored, incentivized, or paid-for reviews. If a brand gave you the product for free or paid you in any form, it does not belong here.",
  },
  { type: "h2", text: "Use your own words and photos" },
  {
    type: "p",
    text: "Write it yourself and use photos you took. Copied text, stock images, and photos lifted from a listing are not allowed — and are checked for.",
  },
  { type: "h2", text: "Be specific and fair" },
  {
    type: "p",
    text: "Say what happened and why. A clear “Hard pass” with reasons is welcome; vague praise and pile-ons are not.",
  },
  { type: "h2", text: "Be respectful" },
  {
    type: "p",
    text: "Critique products, not people. No harassment, hate, or personal attacks — on reviewers, sellers, or anyone in comments and Q&A.",
  },
  { type: "h2", text: "No manipulation" },
  {
    type: "p",
    text: "No fake accounts, vote manipulation, spam, or schemes to inflate earnings or trust. The only monetized links allowed are the affiliate links bluntly attaches.",
  },
  { type: "h2", text: "What happens if you break the rules" },
  {
    type: "p",
    text: "Depending on severity, content may be removed, earnings withheld, trust standing reduced, or accounts suspended. We would always rather help you get it right — reach out if you are unsure.",
  },
];

export default function GuidelinesPage() {
  return (
    <PageShell>
      <Article title="Community Guidelines" blocks={BLOCKS} />
    </PageShell>
  );
}
