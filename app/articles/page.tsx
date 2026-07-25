import type { Metadata } from "next";
import Link from "next/link";

import { Article, type Block } from "@/components/site/Article";
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
          <Link
            href="/search"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-6 text-[14px] font-semibold text-white shadow-[var(--shadow-card)] transition-colors hover:bg-[var(--accent-primary-strong)]"
          >
            Browse reviews
          </Link>
          <Link
            href="/how-it-works"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-6 text-[14px] font-semibold text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] transition-colors hover:text-[var(--accent-primary)]"
          >
            How bluntly works
          </Link>
        </div>
      </Article>
    </PageShell>
  );
}
