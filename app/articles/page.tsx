import type { Metadata } from "next";

import { Article, type Block } from "@/components/site/Article";
import { CtaLink } from "@/components/ui/CtaLink";
import { PageShell } from "@/components/site/PageShell";

export const metadata: Metadata = {
  title: "Articles — bluntly",
  description:
    "Guides, explainers, and shopping breakdowns from the bluntly team — coming soon.",
};

const BLOCKS: Block[] = [
  {
    type: "lead",
    text: "Guides, explainers, and shopping breakdowns from the bluntly team.",
  },
  {
    type: "p",
    text: "We are still writing our first pieces — practical guides on shopping smarter in the Philippines, spotting fake reviews, and getting the most out of every peso. They will land here soon.",
  },
  {
    type: "p",
    text: "In the meantime, the honest reviews already on bluntly are the best place to start.",
  },
];

export default function ArticlesPage() {
  return (
    <PageShell>
      <Article title="Articles" blocks={BLOCKS}>
        <div className="mt-8 flex flex-wrap gap-3">
          <CtaLink href="/search">
            Browse reviews
          </CtaLink>
          <CtaLink href="/how-it-works" variant="secondary">
            How bluntly works
          </CtaLink>
        </div>
      </Article>
    </PageShell>
  );
}
