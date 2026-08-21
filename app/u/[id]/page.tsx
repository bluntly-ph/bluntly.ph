import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ReviewCard } from "@/components/review/ReviewCard";
import { PageShell } from "@/components/site/PageShell";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { getAuthorProfile } from "@/lib/reviews";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const data = await getAuthorProfile(id);
  const name = data?.author.name ?? "Reviewer";
  return {
    title: `${name} — bluntly`,
    description: data ? `Honest reviews by ${name} on bluntly.` : undefined,
  };
}

/** Stable 0–359 hue from a string, for the placeholder avatar tint. */
function hue(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) h = (h * 31 + seed.charCodeAt(i)) % 360;
  return h;
}

export default async function ReviewerProfilePage({ params }: Params) {
  const { id } = await params;
  const data = await getAuthorProfile(id);

  // `notFound()` rather than rendering the message inline, which returned 200.
  // `/u/{id}` accepts any id, so a soft 404 here meant every made-up id was a
  // real, indexable page; Next injects `<meta name="robots" content="noindex">`
  // only for responses that actually 404. The wording lives in
  // `not-found.tsx` beside this file.
  if (!data) notFound();

  const { author, cards } = data;

  return (
    <PageShell width="wide">
      <section className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <span
          aria-hidden="true"
          className="grid h-20 w-20 shrink-0 place-items-center rounded-full text-[26px] font-bold text-white ring-1 ring-[var(--line-hairline-10)]"
          style={{ background: `hsl(${hue(author.name)} 55% 55%)` }}
        >
          {author.name.slice(0, 1).toUpperCase()}
        </span>
        <div className="flex-1">
          <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
            {author.name}
          </h1>
          {author.username ? (
            <p className="text-[14px] text-[var(--text-secondary)]">
              @{author.username}
            </p>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <TrustBadge
              levelName={author.trust}
              stage={author.trustStage}
              score={author.trustScore}
            />
            <span className="rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-3 py-1 text-[12px] text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]">
              {cards.length} {cards.length === 1 ? "review" : "reviews"}
            </span>
          </div>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Reviews</h2>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 md:gap-6 lg:grid-cols-4">
          {cards.map((r) => (
            <ReviewCard key={r.id} review={r} />
          ))}
        </div>
      </section>
    </PageShell>
  );
}
