import type { Metadata } from "next";
import Link from "next/link";
import { ImageSquare, ShieldCheck, Star } from "@phosphor-icons/react/dist/ssr";

import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { Unavailable } from "@/components/site/Unavailable";
import { getUser } from "@/lib/dal";
import { getComparison, peso, type ComparisonEntry } from "@/lib/products";

export const metadata: Metadata = {
  title: "Compare products — bluntly",
};

const MIN = 2;
const MAX = 4;

/**
 * FR-2's side-by-side product comparison.
 *
 * Products are selected by id in the query string (`?ids=a,b,c`), which makes
 * a comparison a shareable link — the natural thing to send a friend who asked
 * "which of these two". That is also why a missing product degrades to a note
 * rather than a 404: a shared link outliving one of its products is ordinary,
 * and losing the other columns to it would be the wrong trade.
 *
 * Seller ratings are absent even though FR-2 names them. Seller reviews were
 * withdrawn from contract on 2026-07-28, so there is no truthful value to put
 * in that row — and inventing one on a platform about honest reviews is not a
 * shortcut worth taking.
 */
export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ ids?: string }>;
}) {
  const { ids = "" } = await searchParams;
  const requested = ids.split(",").map((s) => s.trim()).filter(Boolean);

  const [me, comparison] = await Promise.all([
    getUser().catch(() => null),
    requested.length >= MIN && requested.length <= MAX
      ? getComparison(requested)
      : Promise.resolve(null),
  ]);
  const user: HeaderUser = me
    ? { username: me.username, avatarUrl: me.avatar_url }
    : null;

  const wrongCount = requested.length < MIN || requested.length > MAX;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto flex w-full max-w-[72rem] flex-1 flex-col px-6 py-8 lg:py-10">
        <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
          Compare products
        </h1>
        <p className="mt-1 max-w-[46rem] text-[14px] text-[var(--text-secondary)]">
          Verified review scores and what buyers here actually paid, side by
          side.
        </p>

        {wrongCount ? (
          <EmptyState />
        ) : comparison === null ? (
          <div className="mt-6">
            <Unavailable what="the comparison" />
          </div>
        ) : comparison.entries.length === 0 ? (
          <EmptyState note="None of those products exist any more." />
        ) : (
          <>
            {comparison.not_found.length > 0 ? (
              <p
                role="status"
                className="mt-4 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-primary)_10%,transparent)] px-4 py-3 text-[13px] text-[var(--text-secondary)]"
              >
                {comparison.not_found.length} of the products in this link
                {comparison.not_found.length === 1 ? " is" : " are"} no longer
                available. Showing the rest.
              </p>
            ) : null}

            {/* Horizontal scroll is confined to this container so the page
                body never scrolls sideways on a phone. */}
            <div className="-mx-6 mt-6 overflow-x-auto px-6 lg:mx-0 lg:px-0">
              <ul
                className="flex w-max gap-4 lg:w-full"
                style={{ minWidth: "min(100%, 100%)" }}
              >
                {comparison.entries.map((entry) => (
                  <li
                    key={entry.product.id}
                    className="flex w-[16rem] shrink-0 flex-col rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)] lg:w-full"
                  >
                    <Column entry={entry} />
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

function Column({ entry }: { entry: ComparisonEntry }) {
  const { product, price } = entry;
  return (
    <>
      <div className="relative h-[120px] w-full overflow-hidden rounded-[var(--radius-sm)] bg-[var(--surface-app)]">
        {product.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.image_url}
            alt=""
            loading="lazy"
            decoding="async"
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <div aria-hidden="true" className="absolute inset-0 grid place-items-center">
            <ImageSquare size={28} weight="light" className="text-[var(--text-muted)]" />
          </div>
        )}
      </div>

      <h2 className="mt-3 text-[15px] font-semibold text-[var(--text-primary)]">
        {product.canonical_name ?? "Unnamed product"}
      </h2>
      {product.category ? (
        <p className="mt-0.5 text-[12px] capitalize text-[var(--text-muted)]">
          {product.category}
        </p>
      ) : null}

      <dl className="mt-3 flex flex-col gap-2 text-[13px]">
        <Row label="Rating">
          {entry.avg_rating ? (
            <span className="inline-flex items-center gap-1">
              <Star size={13} weight="fill" className="text-[var(--accent-primary)]" aria-hidden="true" />
              {Number(entry.avg_rating).toFixed(1)}
            </span>
          ) : (
            <Missing />
          )}
        </Row>
        <Row label="Verified reviews">
          {entry.verified_review_count > 0 ? (
            <span className="inline-flex items-center gap-1">
              <ShieldCheck size={13} weight="fill" className="text-[var(--accent-trust)]" aria-hidden="true" />
              {entry.verified_review_count}
            </span>
          ) : (
            <Missing />
          )}
        </Row>
        <Row label="Reviews">
          {entry.review_count > 0 ? entry.review_count : <Missing />}
        </Row>
        <Row label="What buyers paid">
          {price.sufficient ? (
            <span>
              {peso(price.low)} – {peso(price.high)}
            </span>
          ) : (
            <span className="text-[var(--text-muted)]">
              {price.observation_count === 0
                ? "No reports yet"
                : `${price.independent_count}/${price.required_independent} reports`}
            </span>
          )}
        </Row>
        <Row label="Typical price">
          {price.sufficient ? peso(price.median) : <Missing />}
        </Row>
      </dl>

      <Link
        href={`/search?q=${encodeURIComponent(product.canonical_name ?? "")}`}
        className="-mx-1 mt-4 inline-flex items-center justify-center rounded-[var(--radius-pill)] px-3 py-2.5 text-[13px] font-medium text-[var(--accent-primary)] hover:bg-[color-mix(in_srgb,var(--accent-primary)_10%,transparent)]"
      >
        Read the reviews
      </Link>
    </>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[var(--line-hairline-10)] pb-2 last:border-0">
      <dt className="text-[var(--text-secondary)]">{label}</dt>
      <dd className="text-right font-medium text-[var(--text-primary)]">{children}</dd>
    </div>
  );
}

/** One shared marker so a blank cell never reads as a zero. */
function Missing() {
  return (
    <span className="text-[var(--text-muted)]" title="No data yet">
      —
    </span>
  );
}

function EmptyState({ note }: { note?: string } = {}) {
  return (
    <div className="mt-6 flex flex-1 flex-col items-center justify-center rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-10 text-center shadow-[var(--shadow-hairline-inset)]">
      <p className="text-[15px] font-semibold text-[var(--text-primary)]">
        {note ?? `Pick ${MIN} to ${MAX} products to compare`}
      </p>
      <p className="mt-1 max-w-[26rem] text-[14px] text-[var(--text-secondary)]">
        Search for a product and use &ldquo;Compare&rdquo; on its review, or
        share a link like <code>/compare?ids=…</code>.
      </p>
      <Link
        href="/search"
        className="mt-4 inline-flex items-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-4 py-2.5 text-[13px] font-medium text-white"
      >
        Find products
      </Link>
    </div>
  );
}
