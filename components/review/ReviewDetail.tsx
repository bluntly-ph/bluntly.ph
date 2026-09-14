import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
  ChartLine,
  ChatText,
  Check,
  ImageSquare,
  Info,
  MagnifyingGlass,
  SealCheck,
  ShieldCheck,
  ShoppingBag,
  Star,
  ThumbsDown,
  ThumbsUp,
  UserCircle,
  X,
} from "@phosphor-icons/react/dist/ssr";

import { ReadingTelemetry } from "@/components/review/ReadingTelemetry";
import { showsTrustBadge } from "@/components/review/trust-badge-model";
import { disclosureLabel } from "@/components/reviews/disclosure-model";
import { ReportDialog } from "@/components/review/ReportDialog";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { ReviewOverflowMenu } from "@/components/review/ReviewOverflowMenu";
import { ReviewVoteBar } from "@/components/review/ReviewVoteBar";
import { ShareButton } from "@/components/review/ShareButton";
import {
  ageLabel,
  splitHeadline,
  usablePhoto,
  type ReviewFull,
  type Verdict,
} from "@/lib/reviews";

const VERDICT: Record<Verdict, { label: string; className: string; Icon: typeof ThumbsUp }> = {
  yes_absolutely: {
    label: "Yes, absolutely",
    className: "bg-[color-mix(in_srgb,var(--accent-success)_14%,transparent)] text-[var(--accent-success)]",
    Icon: ThumbsUp,
  },
  it_depends: {
    label: "It depends",
    className: "bg-[color-mix(in_srgb,var(--accent-star)_18%,transparent)] text-[var(--base-ink-700)]",
    Icon: ShieldCheck,
  },
  hard_pass: {
    label: "Hard pass",
    className: "bg-[color-mix(in_srgb,var(--accent-danger)_12%,transparent)] text-[var(--accent-danger)]",
    Icon: ThumbsDown,
  },
};

/**
 * The reviewer's photo, or a clean branded placeholder when none.
 *
 * Phone: "Review page.png" draws a 358px square white card at radius 16 with the
 * product contained in it. The frame's "1/3" badge and dots belong to a
 * carousel; a review carries one photo, so neither is drawn. From `md` the
 * wide crop stays: a square at tablet width would be 672px tall.
 *
 * The hero is this page's LCP element, so it is the one image that loads
 * eagerly.
 */
function ReviewHero({ review }: { review: ReviewFull["review"] }) {
  const photo = usablePhoto(review.photo_url);
  if (photo) {
    return (
      <div className="relative mt-[11px] aspect-square w-full overflow-hidden rounded-[16px] bg-[var(--surface-card)] md:mt-6 md:aspect-[16/10] md:rounded-[var(--radius-sm)] lg:max-h-[22rem]">
        <Image
          src={photo}
          alt={review.title}
          fill
          sizes="(min-width: 1024px) 50rem, 100vw"
          priority
          className="object-contain md:object-cover"
        />
      </div>
    );
  }
  return (
    <div
      aria-hidden="true"
      className="mt-[11px] grid aspect-square w-full place-items-center rounded-[16px] md:mt-6 md:aspect-[16/10] md:rounded-[var(--radius-sm)] lg:aspect-[16/7]"
      style={{
        background: `linear-gradient(150deg, hsl(20 42% 74%), hsl(30 38% 55%))`,
      }}
    >
      <ImageSquare size={40} weight="light" className="text-white/55" />
    </div>
  );
}

export function ReviewDetail({
  data,
  canVote,
  isOwnReview = false,
}: {
  data: ReviewFull;
  canVote: boolean;
  /** The author can't report their own review — the API rejects self-reports. */
  isOwnReview?: boolean;
}) {
  const { review, author, product } = data;
  const verdict = VERDICT[review.verdict] ?? VERDICT.it_depends;
  const authorName = author?.display_name || author?.username || "reviewer";
  const hasPros = (review.pros?.length ?? 0) > 0;
  const hasCons = (review.cons?.length ?? 0) > 0;
  const headline = splitHeadline(review.title, product?.canonical_name);

  return (
    <>
      {/* Renders nothing. One per review detail, keyed implicitly by the prop
          it takes — a new review.id on this same route re-runs its whole
          lifecycle as a fresh impression. */}
      <ReadingTelemetry reviewId={review.id} />

      {/* MOBILE chrome only. The frame gives the review its own brand-orange
          bar, and on a phone it is right: it replaces the site header rather
          than stacking under it, and the back control is the way out. Sticky so
          that survives a 2,273px scroll. The five controls are the BUG-012 set.
          The #d9d9d9 strip above it in the mockup is the phone status bar, i.e.
          device chrome, so it is deliberately not built.

          Hidden from `md` up, where the page renders SiteHeader instead: a
          768px tablet showing a phone's back-arrow bar is the same mistake as
          the desktop one, just less obvious. Carrying
          the phone bar onto a 1440px desktop was the whole reason that width
          read as a blown-up mobile layout: no wordmark, no nav, no search, and
          a back arrow where the site's own navigation belongs. */}
      <nav
        aria-label="Review"
        className="sticky top-0 z-30 flex h-[72px] items-center justify-between bg-[var(--accent-primary)] px-4 text-white md:hidden"
      >
        {/* "Review page.png": a full back arrow, then search, bag, "..." and
            the account, in that order, about 48px apart. */}
        <Link
          href="/"
          aria-label="Back"
          className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15"
        >
          <ArrowLeft size={26} />
        </Link>

        <div className="flex items-center gap-2">
          <Link
            href="/search"
            aria-label="Search reviews"
            className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15"
          >
            <MagnifyingGlass size={24} />
          </Link>
          {review.referral_redirect_url ? (
            <a
              href={review.referral_redirect_url}
              target="_blank"
              rel="nofollow sponsored noopener noreferrer"
              aria-label="Buy this product"
              data-telemetry-outlink
              data-telemetry-review-id={review.id}
              className="grid h-10 w-10 place-items-center rounded-full hover:bg-white/15"
            >
              <ShoppingBag size={24} />
            </a>
          ) : null}
          <ReviewOverflowMenu
            title={review.title}
            reviewId={review.id}
            canReport={!isOwnReview}
            onBar
          />
          {/* The frame leaves a wider gap before the account than between the
              other three controls. */}
          <Link
            href="/profile"
            aria-label="Your profile"
            className="ml-[10px] grid h-10 w-10 place-items-center rounded-full hover:bg-white/15"
          >
            <UserCircle size={28} />
          </Link>
        </div>
      </nav>

      <article className="mx-auto w-full max-w-[44rem] px-4 pb-6 pt-5 md:py-6 lg:mx-0 lg:max-w-[42rem] lg:px-0 lg:py-0">
      {/* Product context. Not in the phone frame, which goes straight to the
          author; kept from `md` up, where it orients a reader arriving cold. */}
      {product ? (
        <div className="mt-5 hidden flex-wrap items-center gap-2 text-[12px] text-[var(--text-muted)] md:flex">
          {product.category ? (
            <span className="rounded-[var(--radius-md)] bg-[var(--surface-card)] px-2.5 py-1 capitalize text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]">
              {product.category}
            </span>
          ) : null}
          {product.canonical_name ? <span>{product.canonical_name}</span> : null}
        </div>
      ) : null}

      {/* Author, as the frame draws it: a 24px disc 20px under the bar, then
          "name • shield score • level" at 13px. The age is kept from `md` up. */}
      <div className="flex items-center gap-[9px] md:mt-4 md:gap-2">
        <span
          aria-hidden="true"
          className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-[10px] font-semibold text-white md:h-9 md:w-9 md:text-[13px]"
          style={{ background: "hsl(24 55% 55%)" }}
        >
          {authorName.slice(0, 1).toUpperCase()}
        </span>
        <span className="flex min-w-0 flex-wrap items-center gap-x-1.5 font-[family-name:var(--font-system)] text-[13px] text-[var(--text-primary)]">
          {author?.id ? (
            <Link href={`/u/${author.id}`} className="hover:text-[var(--accent-primary)]">
              {author.username ?? authorName}
            </Link>
          ) : (
            <span>{authorName}</span>
          )}
          {author ? (
            <>
              <span aria-hidden="true" className="text-[var(--text-muted)]">
                •
              </span>
              <TrustBadge
                levelName={author.trust_level_name}
                stage={author.trust_stage}
                score={author.reputation_score}
                plain
                compact
              />
              {author.trust_level_name ? (
                <>
                  <span aria-hidden="true" className="text-[var(--text-muted)]">
                    •
                  </span>
                  <span aria-hidden="true">{author.trust_level_name}</span>
                </>
              ) : null}
            </>
          ) : null}
          <span className="hidden text-[12px] text-[var(--text-muted)] md:inline">
            · {ageLabel(review.created_at)}
          </span>
        </span>
      </div>

      {/* The product in bold with its hyphen, the rest in italic — the frame's
          split. splitHeadline honours the reviewer's own dash and falls back to
          the canonical product name. */}
      <h1 className="mt-[14px] text-[20px] font-normal leading-[25px] text-[var(--text-primary)] md:mt-5 lg:text-[26px] lg:leading-[normal]">
        {headline.product ? (
          <>
            <span className="font-bold">{headline.product} -</span>{" "}
            <span className="italic">{headline.rest}</span>
          </>
        ) : (
          <span className="font-bold">{review.title}</span>
        )}
      </h1>

      {/* A 2px rule, then the frame's pill row. "Price History" jumps to the
          price panel and "Ask a question" opens the question composer.
          "3D Model" is not drawn: no product carries 3D or 360 assets (X.3). */}
      <hr className="mt-[23px] border-0 border-t-2 border-[#d3d3d3]" />
      <div className="-mx-4 mt-[11px] flex gap-[6px] overflow-x-auto px-4 [scrollbar-width:none] lg:mx-0 lg:px-0">
        {product ? (
          <a
            href="#price-history"
            className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-[var(--radius-pill)] border border-[var(--text-primary)] px-3 font-[family-name:var(--font-system)] text-[13px] text-[var(--text-primary)] no-underline hover:border-[var(--accent-primary)] lg:hidden"
          >
            <ChartLine size={16} aria-hidden="true" /> Price History
          </a>
        ) : null}
        <Link
          href="/questions/new"
          className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-[var(--radius-pill)] border border-[var(--text-primary)] px-3 font-[family-name:var(--font-system)] text-[13px] text-[var(--text-primary)] no-underline hover:border-[var(--accent-primary)]"
        >
          <ChatText size={16} aria-hidden="true" /> Ask a question
        </Link>
      </div>

      <ReviewHero review={review} />

      {/* Verdict, stars, verification (X.2) and disclosure (X.1). The frame
          places verdict and rating further down; these stay directly under the
          photo because the verification and the disclosure qualify everything
          a reader is about to read. */}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <span
          className={`inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1.5 text-[13px] font-semibold ${verdict.className}`}
        >
          <verdict.Icon size={16} weight="fill" />
          {verdict.label}
        </span>
        <Stars rating={review.star_rating} />
        {/* X.2: proof + moderator decision + publication, decided by the API. */}
        {showsTrustBadge(review) ? (
          <span className="inline-flex items-center gap-1 text-[12px] text-[var(--accent-success)]">
            <SealCheck size={15} weight="fill" />
            Verified purchase
          </span>
        ) : null}
        {/* Disclosure (X.1): shown whenever the reviewer declared a relationship,
            next to the verification it qualifies. */}
        {disclosureLabel(review.material_relationship) ? (
          <span className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] bg-[color-mix(in_srgb,var(--accent-trust)_12%,transparent)] px-2.5 py-1 text-[12px] font-medium text-[var(--text-primary)]">
            <Info size={14} aria-hidden="true" className="text-[var(--accent-trust)]" />
            {disclosureLabel(review.material_relationship)}
          </span>
        ) : null}
      </div>

      {/* Body. `id="review-body"` is the element ReadingTelemetry observes for
          both "is the discussion in view" (IntersectionObserver) and the
          scroll read-through fraction — design §4.3/§4.4. */}
      <Section title="The review">
        <p id="review-body" className="whitespace-pre-line">{review.discussion}</p>
      </Section>

      {review.verdict_explanation ? (
        <Section title="Verdict">
          <p className="whitespace-pre-line">{review.verdict_explanation}</p>
        </Section>
      ) : null}

      {review.target_audience ? (
        <Section title="Best for">
          <p>{review.target_audience}</p>
        </Section>
      ) : null}

      {review.anti_target_audience ? (
        <Section title="This is not for">
          <p>{review.anti_target_audience}</p>
        </Section>
      ) : null}

      {hasPros || hasCons ? (
        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          {hasPros ? (
            <ProsCons kind="pro" items={review.pros ?? []} />
          ) : null}
          {hasCons ? (
            <ProsCons kind="con" items={review.cons ?? []} />
          ) : null}
        </div>
      ) : null}

      {review.price_paid ? (
        <p className="mt-6 text-[13px] text-[var(--text-secondary)]">
          Paid <span className="font-semibold text-[var(--text-primary)]">₱{review.price_paid}</span>
        </p>
      ) : null}

      {/* Action bar */}
      <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-[var(--border-subtle)] pt-6">
        <ReviewVoteBar
          reviewId={review.id}
          helpful={review.helpful_votes}
          unhelpful={review.unhelpful_votes}
          canVote={canVote}
          myVote={review.my_vote}
        />

        {/* Hidden at `lg`: the sidebar's product card carries the Buy action on
            desktop, and two identical primary CTAs on one screen is a choice
            the reader has to make for no reason. */}
        {review.referral_redirect_url ? (
          <a
            href={review.referral_redirect_url}
            target="_blank"
            rel="noopener noreferrer nofollow sponsored"
            data-telemetry-outlink
            data-telemetry-review-id={review.id}
            className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-5 py-2.5 text-[13px] font-semibold text-white hover:bg-[var(--accent-primary-strong)] lg:hidden"
          >
            <ShoppingBag size={16} weight="fill" />
            Buy it here
          </a>
        ) : (
          <span
            className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--line-hairline-30)] px-5 py-2.5 text-[13px] font-semibold text-[var(--text-muted)] lg:hidden"
            title="An affiliate link is added once a moderator approves this review."
          >
            <ShoppingBag size={16} />
            Buy link pending
          </span>
        )}

        <div className="ml-auto flex items-center gap-1">
          <ShareButton title={review.title} reviewId={review.id} />

          {!isOwnReview ? (
            <ReportDialog reviewId={review.id} canReport={canVote} />
          ) : null}
        </div>
      </div>
      </article>
    </>
  );
}

function Stars({ rating }: { rating: number }) {
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${rating} out of 5 stars`}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          size={18}
          weight={i < rating ? "fill" : "regular"}
          className={i < rating ? "text-[var(--accent-star)]" : "text-[var(--base-gray-300)]"}
        />
      ))}
    </span>
  );
}

/**
 * A titled block of the review body.
 *
 * The frame writes these as 16px SemiBold in full ink over 14px/22px Light —
 * a plain sentence-case heading, not the 13px uppercase muted label this used.
 * Uppercase tracking reads as a form field; these are section titles in a piece
 * of writing.
 */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
        {title}
      </h2>
      <div className="mt-3 text-[14px] font-light leading-[22px] text-[var(--text-primary)]">
        {children}
      </div>
    </section>
  );
}

function ProsCons({ kind, items }: { kind: "pro" | "con"; items: string[] }) {
  const isPro = kind === "pro";
  return (
    <div>
      <h3 className="text-[16px] font-semibold text-[var(--text-primary)]">
        {isPro ? "Pros" : "Cons"}
      </h3>
      <ul className="mt-3 flex flex-col gap-2.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-3 text-[12px] text-[var(--text-primary)]">
            {/* 44px ringed circle, as drawn — the frame gives each point a
                substantial marker rather than a small inline tick, which is
                what makes the pro/con columns scannable at a glance. */}
            <span
              className={`grid h-11 w-11 shrink-0 place-items-center rounded-full ring-1 ${
                isPro
                  ? "text-[var(--accent-success)] ring-[color-mix(in_srgb,var(--accent-success)_35%,transparent)]"
                  : "text-[var(--accent-danger)] ring-[color-mix(in_srgb,var(--accent-danger)_35%,transparent)]"
              }`}
            >
              {isPro ? <Check size={22} weight="bold" /> : <X size={22} weight="bold" />}
            </span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ReviewDetail;
