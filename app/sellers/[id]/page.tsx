import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SealCheck, ShieldWarning, Star } from "@phosphor-icons/react/dist/ssr";

import { SellerReviewForm } from "@/components/seller/SellerReviewForm";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { getUser } from "@/lib/dal";
import { getSeller } from "@/lib/sellers";

export const metadata: Metadata = {
  title: "Seller — bluntly",
};

const pct = (v: number | null) => (v == null ? "—" : `${Math.round(v)}%`);
const avg = (v: number | null) => (v == null ? "—" : v.toFixed(1));

export default async function SellerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { profile, reviews } = await getSeller(id);
  if (!profile) notFound();

  let user: HeaderUser = null;
  let canReview = false;
  try {
    const me = await getUser();
    if (me) {
      user = { username: me.username, avatarUrl: me.avatar_url };
      canReview = me.id !== id;
    }
  } catch {
    user = null;
  }

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto w-full max-w-[52rem] flex-1 px-6 py-8 lg:py-10">
        <div className="flex flex-wrap items-center gap-3">
          <span
            className="grid h-16 w-16 shrink-0 place-items-center rounded-[var(--radius-sm)] text-[22px] font-bold text-white"
            style={{ background: "hsl(210 45% 45%)" }}
          >
            {(profile.display_name ?? "S").slice(0, 1).toUpperCase()}
          </span>
          <div className="flex-1">
            <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
              {profile.display_name ?? "Seller"}
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 text-[13px] text-[var(--accent-success)]">
                <SealCheck size={15} weight="fill" />
                {profile.seller_trust_score
                  ? `${Math.round(Number(profile.seller_trust_score) * 100)}% seller trust`
                  : "New seller"}
              </span>
              <span className="text-[13px] text-[var(--text-muted)]">
                · {profile.review_count} buyer rating{profile.review_count === 1 ? "" : "s"}
              </span>
              {profile.low_trust ? (
                <span className="inline-flex items-center gap-1 rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--accent-danger)_12%,transparent)] px-2 py-0.5 text-[12px] text-[var(--accent-danger)]">
                  <ShieldWarning size={13} weight="fill" /> Low trust
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {/* Dimension aggregates */}
        <section className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Dim label="Accuracy" value={pct(profile.accuracy_pct)} />
          <Dim label="Complete orders" value={pct(profile.completeness_pct)} />
          <Dim label="Service" value={avg(profile.customer_service_avg)} suffix="/5" />
          <Dim label="Packaging" value={avg(profile.packaging_avg)} suffix="/5" />
          <Dim label="Recommend" value={pct(profile.recommend_pct)} />
        </section>

        <div className="mt-8">
          <SellerReviewForm sellerId={id} canReview={canReview} />
        </div>

        <section className="mt-10">
          <h2 className="text-[18px] font-bold text-[var(--text-primary)]">Buyer ratings</h2>
          {reviews.length > 0 ? (
            <ul className="mt-4 flex flex-col gap-3">
              {reviews.map((r) => (
                <li key={r.id} className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-hairline-inset)]">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-[var(--text-secondary)]">
                    <span className="inline-flex items-center gap-1 font-medium text-[var(--text-primary)]">
                      <Star size={15} weight="fill" className="text-[var(--accent-star)]" />
                      {r.overall_rating}/5
                    </span>
                    <span>{r.accuracy ? "✓ Accurate" : "✗ Not as described"}</span>
                    <span>{r.order_completeness ? "✓ Complete" : "✗ Missing items"}</span>
                    <span>Service {r.customer_service}/5</span>
                    <span>Packaging {r.packaging_quality}/5</span>
                    <span className="ml-auto text-[12px] text-[var(--text-muted)]">
                      {new Date(r.created_at).toLocaleDateString("en-PH")}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-[14px] text-[var(--text-secondary)]">
              No buyer ratings yet — be the first to rate this seller.
            </p>
          )}
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

function Dim({ label, value, suffix }: { label: string; value: string; suffix?: string }) {
  return (
    <div className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-3 text-center shadow-[var(--shadow-hairline-inset)]">
      <div className="text-[20px] font-bold text-[var(--text-primary)]">
        {value}
        {suffix ? <span className="text-[13px] text-[var(--text-muted)]">{suffix}</span> : null}
      </div>
      <div className="mt-0.5 text-[11px] text-[var(--text-muted)]">{label}</div>
    </div>
  );
}
