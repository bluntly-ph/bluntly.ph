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
import { ageLabel, usablePhoto, type ReviewFull, type Verdict } from "@/lib/reviews";

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

  return (
    <article className="mx-auto w-full max-w-[44rem] px-6 py-6 lg:py-10">
      {/* Top nav (BUG-012). The frame draws five controls here; only Back was
          rendered, so from a review there was no way to search, reach the
          listing, or get to your own profile without going home first. The
          overflow menu carries report and share, which also live in the action
          row below — this bar is the reach-anywhere copy, not a second home
          for them. */}
      <nav aria-label="Review" className="flex items-center justify-between">
        <Link
          href="/"
          aria-label="Back"
          className="inline-flex items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <CaretLeft size={18} /> Back
        </Link>

        <div className="flex items-center gap-1">
          <Link
            href="/search"
            aria-label="Search reviews"
            className="grid h-9 w-9 place-items-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] hover:text-[var(--text-primary)]"
          >
            <MagnifyingGlass size={18} />
          </Link>
          {review.referral_redirect_url ? (
            <a
              href={review.referral_redirect_url}
              target="_blank"
              rel="nofollow sponsored noopener noreferrer"
              aria-label="Buy this product"
              className="grid h-9 w-9 place-items-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] hover:text-[var(--text-primary)]"
            >
              <ShoppingBag size={18} />
            </a>
          ) : null}
          <ReviewOverflowMenu
            title={review.title}
            reviewId={review.id}
            canReport={!isOwnReview}
          />
          <Link
            href="/profile"
            aria-label="Your profile"
            className="grid h-9 w-9 place-items-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] hover:text-[var(--text-primary)]"
          >
            <UserCircle size={22} />
          </Link>
        </div>
      </nav>

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
      <h1 className="mt-4 text-[24px] font-bold leading-tight text-[var(--text-primary)] lg:text-[30px]">
        {review.title}
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
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={usablePhoto(review.photo_url) as string}
          alt={review.title}
          className="mt-6 aspect-[16/10] w-full rounded-[var(--radius-sm)] object-cover"
        />
      ) : (
        <div
          aria-hidden="true"
          className="mt-6 grid aspect-[16/10] w-full place-items-center rounded-[var(--radius-sm)]"
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

        {review.referral_redirect_url ? (
          <a
            href={review.referral_redirect_url}
            target="_blank"
            rel="noopener noreferrer nofollow sponsored"
            className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-5 py-2.5 text-[13px] font-semibold text-white hover:bg-[var(--accent-primary-strong)]"
          >
            <ShoppingBag size={16} weight="fill" />
            Buy it here
          </a>
        ) : (
          <span
            className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--line-hairline-30)] px-5 py-2.5 text-[13px] font-semibold text-[var(--text-muted)]"
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="text-[13px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
        {title}
      </h2>
      <div className="mt-2 text-[15px] leading-relaxed text-[var(--text-primary)]">
        {children}
      </div>
    </section>
  );
}

function ProsCons({ kind, items }: { kind: "pro" | "con"; items: string[] }) {
  const isPro = kind === "pro";
  return (
    <div>
      <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">
        {isPro ? "Pros" : "Cons"}
      </h3>
      <ul className="mt-3 flex flex-col gap-2.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-[14px] text-[var(--text-secondary)]">
            <span
              className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full ${
                isPro
                  ? "bg-[color-mix(in_srgb,var(--accent-success)_16%,transparent)] text-[var(--accent-success)]"
                  : "bg-[color-mix(in_srgb,var(--accent-danger)_14%,transparent)] text-[var(--accent-danger)]"
              }`}
            >
              {isPro ? <Check size={12} weight="bold" /> : <X size={12} weight="bold" />}
            </span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ReviewDetail;
