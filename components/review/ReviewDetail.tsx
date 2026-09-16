import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
  ChartLine,
  ChatCenteredText,
  Chats,
  Check,
  DotOutline,
  ImageSquare,
  Info,
  MagnifyingGlass,
  SealCheck,
  ShoppingBagOpen,
  UserCircle,
  X,
} from "@phosphor-icons/react/dist/ssr";

import { ReadingTelemetry } from "@/components/review/ReadingTelemetry";
import { showsTrustBadge } from "@/components/review/trust-badge-model";
import { disclosureLabel } from "@/components/reviews/disclosure-model";
import { ReportDialog } from "@/components/review/ReportDialog";
import { ReviewOverflowMenu } from "@/components/review/ReviewOverflowMenu";
import { ReviewVoteBar } from "@/components/review/ReviewVoteBar";
import { ShareButton } from "@/components/review/ShareButton";
import type { HeaderUser } from "@/components/site/SiteHeader";
import { StarRow } from "@/components/sellers/SellerIdentity";
import { HonestyScore } from "@/components/ui/HonestyScore";
import { ageLabel, splitHeadline, usablePhoto, type ReviewFull, type Verdict } from "@/lib/reviews";
import { trustScore } from "@/lib/trust";

/**
 * A published review, built to Figma "Review page" (4218:1196), read from the
 * file on 2026-09-14.
 *
 * Phone values from the frame (status bar excluded): a 72px --accent-primary
 * bar with 28px glyphs — back at x16; search, bag and overflow on a 48px pitch;
 * a 40px avatar at the right gutter. 20px down, a 24px avatar with the byline 8px
 * after it in 12px Poppins Light, split by 12px DotOutline glyphs around the
 * Honesty Score. 12px down, the title in 20px SemiBold on a 30px line with the
 * rest in regular italic; 16px to a 1px rule at 30% ink; 12px to 32px pills in
 * 12px Light with 20px glyphs; 10px to a 358px square photo on #e1e1e1. Sections
 * are a 16px SemiBold heading, 20px to 14px Light on a 21px line, 26px apart.
 * Pros & Cons share one heading over two 158px columns of 44px white discs with
 * 32px light glyphs. "Rating" is five 28px stars. 20px down, the action row: a
 * vote pill, a comment-count pill, "Shop" in the brand outline, and a round
 * Share, then a full-bleed hairline.
 *
 * INTENTIONAL PRODUCT DIFFERENCES:
 *  - "General Info" and "Experience" are one field here (`discussion`), shown
 *    under one heading; "Best for" is kept because the composer collects it.
 *  - The verdict (yes / it depends / hard pass) leads the "Verdict" section,
 *    and verification (X.2) and disclosure (X.1) sit under the photo: both
 *    qualify everything below them.
 *  - "3D Model" is not drawn: no product carries 3D or 360 assets (X.3). The
 *    carousel's "1/3" badge and dots are not drawn: a review carries one photo.
 *  - Pros and cons carry no aspect ("Price", "Portability"), so each point is
 *    its label alone.
 *  - From `md` up there is no frame: the page renders SiteHeader instead of the
 *    orange bar and the photo takes a wide crop.
 */

const VERDICT_LABEL: Record<Verdict, string> = {
  yes_absolutely: "Yes, absolutely.",
  it_depends: "It depends.",
  hard_pass: "Hard pass.",
};

const PILL =
  "inline-flex h-8 shrink-0 items-center gap-1 rounded-[var(--radius-md)] border border-[var(--text-primary)] px-[11px] text-[12px] font-light leading-none text-[var(--text-primary)] no-underline hover:border-[var(--accent-primary)]";

const BAR_BUTTON = "grid h-10 w-10 place-items-center rounded-full hover:bg-white/15";

const Dot = ({ className = "" }: { className?: string }) => (
  <DotOutline size={12} aria-hidden="true" className={`shrink-0 text-[var(--base-gray-400)] ${className}`} />
);

function compact(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}m`;
}

/**
 * The reviewer's photo on the frame's #e1e1e1 media ground, cropped to fill as
 * drawn. The hero is this page's LCP element, so it is the one image that loads
 * eagerly.
 */
function ReviewHero({ review }: { review: ReviewFull["review"] }) {
  const photo = usablePhoto(review.photo_url);
  return (
    <div className="relative mt-2.5 aspect-square w-full overflow-hidden rounded-[16px] bg-[#e1e1e1] md:mt-6 md:aspect-[16/10] md:rounded-[var(--radius-sm)] lg:max-h-[22rem]">
      {photo ? (
        <Image
          src={photo}
          alt={review.title}
          fill
          sizes="(min-width: 1024px) 50rem, 100vw"
          priority
          className="object-cover"
        />
      ) : (
        <div aria-hidden="true" className="absolute inset-0 grid place-items-center">
          <ImageSquare size={40} weight="light" className="text-[var(--base-gray-400)]" />
        </div>
      )}
    </div>
  );
}

export function ReviewDetail({
  data,
  canVote,
  isOwnReview = false,
  viewer = null,
}: {
  data: ReviewFull;
  canVote: boolean;
  /** The author can't report their own review — the API rejects self-reports. */
  isOwnReview?: boolean;
  /** The signed-in reader, for the bar's avatar. */
  viewer?: HeaderUser;
}) {
  const { review, author, product } = data;
  const authorName = author?.display_name || author?.username || "reviewer";
  const authorAvatar = usablePhoto(author?.avatar_url);
  const viewerAvatar = usablePhoto(viewer?.avatarUrl);
  const hasScore = trustScore(author?.reputation_score) !== null;
  const hasPros = (review.pros?.length ?? 0) > 0;
  const hasCons = (review.cons?.length ?? 0) > 0;
  const headline = splitHeadline(review.title, product?.canonical_name);
  const verified = showsTrustBadge(review);
  const disclosure = disclosureLabel(review.material_relationship);
  const commentCount = data.comment_count ?? 0;

  return (
    <>
      {/* Renders nothing. One per review detail, keyed implicitly by the prop
          it takes — a new review.id on this same route re-runs its whole
          lifecycle as a fresh impression. */}
      <ReadingTelemetry reviewId={review.id} />

      {/* Phone chrome only: it replaces the site header rather than stacking
          under it, and sticks through a long read. The #d9d9d9 strip above it in
          the frame is the phone status bar, device chrome, so it is not built.
          Hidden from `md` up, where the page renders SiteHeader instead. */}
      <nav
        aria-label="Review"
        className="sticky top-0 z-30 flex h-[72px] items-center justify-between bg-[var(--accent-primary)] px-4 text-[var(--text-on-brand)] md:hidden"
      >
        <Link href="/" aria-label="Back" className={`-ml-1.5 ${BAR_BUTTON}`}>
          <ArrowLeft size={28} />
        </Link>

        <div className="flex items-center gap-2">
          <Link href="/search" aria-label="Search reviews" className={BAR_BUTTON}>
            <MagnifyingGlass size={28} />
          </Link>
          {review.referral_redirect_url ? (
            <a
              href={review.referral_redirect_url}
              target="_blank"
              rel="nofollow sponsored noopener noreferrer"
              aria-label="Buy this product"
              data-telemetry-outlink
              data-telemetry-review-id={review.id}
              className={BAR_BUTTON}
            >
              <ShoppingBagOpen size={28} />
            </a>
          ) : null}
          <ReviewOverflowMenu title={review.title} reviewId={review.id} canReport={!isOwnReview} onBar />
          {/* The 40px avatar ends on the 16px gutter, 14px past the overflow. */}
          <Link
            href="/profile"
            aria-label="Your profile"
            className="ml-1.5 grid h-10 w-10 place-items-center overflow-hidden rounded-full hover:opacity-90"
          >
            {viewerAvatar ? (
              <Image
                src={viewerAvatar}
                alt=""
                width={40}
                height={40}
                className="h-10 w-10 rounded-full object-cover"
              />
            ) : (
              <UserCircle size={40} weight="light" />
            )}
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

        <div className="flex items-start gap-2 md:mt-4">
          {authorAvatar ? (
            <Image
              src={authorAvatar}
              alt=""
              width={24}
              height={24}
              className="h-6 w-6 shrink-0 rounded-full object-cover"
            />
          ) : (
            <span
              aria-hidden="true"
              className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-[10px] font-semibold text-white"
              style={{ background: "hsl(24 55% 55%)" }}
            >
              {authorName.slice(0, 1).toUpperCase()}
            </span>
          )}
          <p className="mt-[3px] flex min-w-0 flex-wrap items-center gap-x-1 gap-y-1 text-[12px] font-light leading-4 text-[var(--text-primary)]">
            {author?.id ? (
              <Link href={`/u/${author.id}`} className="hover:text-[var(--accent-primary)]">
                {author.username ?? authorName}
              </Link>
            ) : (
              <span>{authorName}</span>
            )}
            {author && hasScore ? (
              <>
                <Dot />
                <HonestyScore
                  score={author.reputation_score}
                  levelName={author.trust_level_name}
                  stage={author.trust_stage}
                />
              </>
            ) : null}
            {author?.trust_level_name ? (
              <>
                <Dot />
                <span>{author.trust_level_name}</span>
              </>
            ) : null}
            <Dot className="hidden md:block" />
            <span className="hidden font-extralight md:inline">{ageLabel(review.created_at)}</span>
          </p>
        </div>

        {/* The phone keeps these in its orange bar. That bar is `md:hidden`, so
            from `md` the same controls — copy the link, report the review —
            live beside the headline instead of disappearing on the website
            (journey audit, 2026-09-16). */}
        <div className="mt-4 hidden items-center gap-2 md:flex">
          <ReviewOverflowMenu title={review.title} reviewId={review.id} canReport={!isOwnReview} />
        </div>

        {/* The product in SemiBold with its hyphen, the rest in regular italic —
            the frame's split. splitHeadline honours the reviewer's own dash and
            falls back to the canonical product name. */}
        <h1 className="mt-3 text-[20px] font-semibold leading-[30px] text-[var(--text-primary)] md:mt-2 lg:text-[26px] lg:leading-[normal]">
          {headline.product ? (
            <>
              {headline.product} - <span className="font-normal italic">{headline.rest}</span>
            </>
          ) : (
            review.title
          )}
        </h1>

        {/* "Price History" jumps to the price panel and "Ask a question" opens
            the question composer. */}
        <hr className="mt-4 border-0 border-t border-[var(--line-hairline-30)]" />
        <div className="-mx-4 mt-[11px] flex gap-3 overflow-x-auto px-4 [scrollbar-width:none] lg:mx-0 lg:px-0">
          {product ? (
            <a href="#price-history" className={`${PILL} lg:hidden`}>
              <ChartLine size={20} aria-hidden="true" /> Price History
            </a>
          ) : null}
          <Link href="/questions/new" className={PILL}>
            <ChatCenteredText size={20} aria-hidden="true" /> Ask a question
          </Link>
        </div>

        <ReviewHero review={review} />

        {verified || disclosure ? (
          <div className="mt-5 flex flex-wrap items-center gap-3">
            {/* X.2: proof + moderator decision + publication, decided by the API. */}
            {verified ? (
              <span className="inline-flex items-center gap-1 text-[12px] text-[var(--accent-success)]">
                <SealCheck size={16} weight="fill" />
                Verified purchase
              </span>
            ) : null}
            {/* X.1: shown whenever the reviewer declared a relationship. */}
            {disclosure ? (
              <span className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] bg-[color-mix(in_srgb,var(--accent-trust)_12%,transparent)] px-2.5 py-1 text-[12px] font-medium text-[var(--text-primary)]">
                <Info size={14} aria-hidden="true" className="text-[var(--accent-trust)]" />
                {disclosure}
              </span>
            ) : null}
          </div>
        ) : null}

        <div className="mt-5 flex flex-col gap-[26px]">
          {/* `id="review-body"` is the element ReadingTelemetry observes for both
              "is the discussion in view" and the scroll read-through fraction —
              design §4.3/§4.4. */}
          <Section title="The review">
            <p id="review-body" className="whitespace-pre-line">
              {review.discussion}
            </p>
          </Section>

          {hasPros || hasCons ? (
            <Section title="Pros & Cons">
              <div className="grid grid-cols-2">
                <PointList kind="pro" items={review.pros ?? []} />
                <PointList kind="con" items={review.cons ?? []} />
              </div>
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

          <Section title="Verdict">
            <p className="whitespace-pre-line">
              <span className="font-semibold">
                {VERDICT_LABEL[review.verdict] ?? VERDICT_LABEL.it_depends}
              </span>
              {review.verdict_explanation ? <> {review.verdict_explanation}</> : null}
            </p>
          </Section>

          <Section title="Rating">
            <StarRow value={review.star_rating} size={28} gap={0} />
            {review.price_paid ? (
              <p className="mt-3 text-[12px]">
                Paid <span className="font-semibold">₱{review.price_paid}</span>
              </p>
            ) : null}
          </Section>
        </div>

        <div className="mt-5 flex items-center gap-2">
          <ReviewVoteBar
            reviewId={review.id}
            helpful={review.helpful_votes}
            unhelpful={review.unhelpful_votes}
            canVote={canVote}
            myVote={review.my_vote}
          />
          <a
            href="#comments"
            aria-label={`${commentCount} ${commentCount === 1 ? "comment" : "comments"}`}
            className="inline-flex h-8 shrink-0 items-center gap-1 rounded-[20px] border border-[var(--line-hairline-30)] px-3 text-[12px] leading-none text-[var(--text-primary)] no-underline hover:bg-[var(--line-hairline-10)]"
          >
            <Chats size={16} aria-hidden="true" />
            <span aria-hidden="true">{compact(commentCount)}</span>
          </a>

          {/* Hidden at `lg`: the sidebar's product card carries the Buy action
              on desktop, and two identical CTAs on one screen is a choice the
              reader has to make for no reason. */}
          {review.referral_redirect_url ? (
            <a
              href={review.referral_redirect_url}
              target="_blank"
              rel="noopener noreferrer nofollow sponsored"
              data-telemetry-outlink
              data-telemetry-review-id={review.id}
              className="ml-auto inline-flex h-8 shrink-0 items-center gap-1 rounded-[20px] border border-[var(--accent-primary)] px-[11px] text-[12px] font-light leading-none text-[var(--accent-primary)] no-underline hover:bg-[color-mix(in_srgb,var(--accent-primary)_8%,transparent)] lg:hidden"
            >
              <ShoppingBagOpen size={20} aria-hidden="true" />
              Shop
            </a>
          ) : (
            <span
              title="An affiliate link is added once a moderator approves this review."
              className="ml-auto inline-flex h-8 shrink-0 items-center gap-1 rounded-[20px] border border-[var(--line-hairline-30)] px-[11px] text-[12px] font-light leading-none text-[var(--text-muted)] lg:hidden"
            >
              <ShoppingBagOpen size={20} aria-hidden="true" />
              Shop
              <span className="sr-only"> — the link appears once a moderator approves this review</span>
            </span>
          )}

          <div className="lg:ml-auto">
            <ShareButton title={review.title} reviewId={review.id} variant="icon" />
          </div>

          {!isOwnReview ? <ReportDialog reviewId={review.id} canReport={canVote} hideTrigger /> : null}
        </div>
      </article>
    </>
  );
}

/**
 * A titled block of the review body: a 16px SemiBold heading, 20px down to
 * 14px Light on a 21px line.
 */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-[16px] font-semibold leading-none text-[var(--text-primary)]">{title}</h2>
      <div className="mt-5 text-[14px] font-light leading-[21px] text-[var(--text-primary)]">{children}</div>
    </section>
  );
}

/**
 * One column of Pros & Cons: 44px white discs 16px apart holding a 32px
 * Phosphor Check or X at light weight (the frame's 1.5px stroke), each with its
 * point in 12px Regular 8px to the right.
 */
function PointList({ kind, items }: { kind: "pro" | "con"; items: string[] }) {
  const isPro = kind === "pro";
  if (items.length === 0) return <div />;
  return (
    <ul aria-label={isPro ? "Pros" : "Cons"} className="flex flex-col gap-4 pr-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-[12px] font-normal leading-4">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[var(--surface-card)] text-[var(--base-black)]">
            {isPro ? (
              <Check size={32} weight="light" aria-label="Pro" />
            ) : (
              <X size={32} weight="light" aria-label="Con" />
            )}
          </span>
          <span className="mt-0.5 min-w-0">{item}</span>
        </li>
      ))}
    </ul>
  );
}

export default ReviewDetail;
