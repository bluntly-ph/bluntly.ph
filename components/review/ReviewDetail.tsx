import Image from "next/image";
import Link from "next/link";
import {
  CaretLeft,
  Check,
  ImageSquare,
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
        <Link
          href="/"
          aria-label="Back"
          className="grid h-9 w-9 place-items-center rounded-full hover:bg-white/15"
        >
          <CaretLeft size={24} />
        </Link>

        <div className="flex items-center gap-1">
          {review.referral_redirect_url ? (
            <a
              href={review.referral_redirect_url}
              target="_blank"
              rel="nofollow sponsored noopener noreferrer"
              aria-label="Buy this product"
              className="grid h-9 w-9 place-items-center rounded-full hover:bg-white/15"
            >
              <ShoppingBag size={22} />
            </a>
          ) : null}
          <ReviewOverflowMenu
            title={review.title}
            reviewId={review.id}
            canReport={!isOwnReview}
            onBar
          />
          <Link
            href="/search"
            aria-label="Search reviews"
            className="grid h-9 w-9 place-items-center rounded-full hover:bg-white/15"
          >
            <MagnifyingGlass size={22} />
          </Link>
          <Link
            href="/profile"
            aria-label="Your profile"
            className="grid h-9 w-9 place-items-center rounded-full hover:bg-white/15"
          >
            <UserCircle size={22} />
          </Link>
        </div>
      </nav>

      <article className="mx-auto w-full max-w-[44rem] px-4 py-6 lg:mx-0 lg:max-w-[42rem] lg:px-0 lg:py-0">
      {/* Product context */}
      {product ? (
        <div className="mt-5 flex flex-wrap items-center gap-2 text-[12px] text-[var(--text-muted)]">
          {product.category ? (
            <span className="rounded-[var(--radius-md)] bg-[var(--surface-card)] px-2.5 py-1 capitalize text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]">
              {product.category}
            </span>
          ) : null}
          {product.canonical_name ? <span>{product.canonical_name}</span> : null}
        </div>
      ) : null}

      {/* Author */}
      <div className="mt-4 flex items-center gap-2">
        <span
          aria-hidden="true"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-[13px] font-semibold text-white"
          style={{ background: "hsl(24 55% 55%)" }}
        >
          {authorName.slice(0, 1).toUpperCase()}
        </span>
        {author?.id ? (
          <Link
            href={`/u/${author.id}`}
            className="text-[14px] font-semibold text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
          >
            {author.username ? `@${author.username}` : authorName}
          </Link>
        ) : (
          <span className="text-[14px] font-semibold text-[var(--text-primary)]">
            {authorName}
          </span>
        )}
        {author ? (
          <TrustBadge
            levelName={author.trust_level_name}
            stage={author.trust_stage}
            score={author.reputation_score}
            plain
          />
        ) : null}
        <span className="text-[12px] text-[var(--text-muted)]">
          · {ageLabel(review.created_at)}
        </span>
      </div>

      {/* Title + verdict + rating */}
      {/* 20px SemiBold, product name then the verdict in italic after a dash —
          the same split the cards use, from the same frame. It was 24px bold
          as one undifferentiated string. splitHeadline honours the reviewer's
          own dash and falls back to the canonical product name. */}
      <h1 className="mt-4 text-[20px] font-semibold leading-[normal] text-[var(--text-primary)] lg:text-[26px]">
        {headline.product ? (
          <>
            {headline.product}
            <span className="font-normal text-[var(--text-muted)]"> — </span>
            <span className="font-normal italic">{headline.rest}</span>
          </>
        ) : (
          review.title
        )}
      </h1>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <span
          className={`inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1.5 text-[13px] font-semibold ${verdict.className}`}
        >
          <verdict.Icon size={16} weight="fill" />
          {verdict.label}
        </span>
        <Stars rating={review.star_rating} />
        {review.verification_status === "verified" ? (
          <span className="inline-flex items-center gap-1 text-[12px] text-[var(--accent-success)]">
            <SealCheck size={15} weight="fill" />
            Verified purchase
          </span>
        ) : null}
      </div>

      {/* The reviewer's proof photo, or a clean branded placeholder when none. */}
      {usablePhoto(review.photo_url) ? (
        /* The hero is this page's LCP element, so it is the one image that
           loads eagerly. The wrapper carries the ratio and the corner radius
           the bare <img> used to carry itself, so the drawn result is
           unchanged. */
        <div className="relative mt-6 aspect-[16/10] w-full overflow-hidden rounded-[var(--radius-sm)] lg:max-h-[22rem]">
          <Image
            src={usablePhoto(review.photo_url) as string}
            alt={review.title}
            fill
            sizes="(min-width: 1024px) 50rem, 100vw"
            priority
            className="object-cover"
          />
        </div>
      ) : (
        <div
          aria-hidden="true"
          className="mt-6 grid aspect-[16/10] w-full place-items-center rounded-[var(--radius-sm)] lg:aspect-[16/7]"
          style={{
            background: `linear-gradient(150deg, hsl(20 42% 74%), hsl(30 38% 55%))`,
          }}
        >
          <ImageSquare size={40} weight="light" className="text-white/55" />
        </div>
      )}

      {/* Body */}
      <Section title="The review">
        <p className="whitespace-pre-line">{review.discussion}</p>
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
          <ShareButton title={review.title} />

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
