"use client";

import Link from "next/link";
import { useId, useRef, useState } from "react";
import { Check, Info, MagnifyingGlass, Star } from "@phosphor-icons/react";

import type { Question } from "@/lib/qa";
import type { SellerReview, SellerSummary } from "@/lib/sellers";

import { TrustBadge } from "@/components/ui/TrustBadge";

import { AskSellerQuestionForm } from "./AskSellerQuestionForm";
import { ReviewerInitial } from "./SellerIdentity";
import { STAR_BAR_COLOUR } from "./SellerRatingSummary";
import { SellerReviewCard } from "./SellerReviewCard";
import { distributionBars, filterSellerReviews, sharePercent, shortAge } from "./seller-model";

/**
 * The store page's "All reviews" block, as "Seller Page - Review.png" and
 * "Seller Page - Questions.png" draw it: the average with a green star, the
 * disclaimer on blue, a five-row star filter with each star's share, a keyword
 * search, and Reviews / Questions tabs over the lists.
 *
 * The filter and search are real, and they run over the reviews this page
 * loaded — the newest 100, the API's ceiling. When a store has more, the list
 * says so rather than implying the filter saw everything.
 *
 * NOT RENDERED: "Read more." in the disclaimer (no page explains it), the
 * "All filters" and "Sort" pills, "Top mentions" chips, and per-review Reply /
 * Share rows. None has a definition or data behind it in this product.
 */

const FACE = "font-[family-name:var(--font-system)]";
const ALL_STARS = [5, 4, 3, 2, 1];

type Tab = "reviews" | "questions";

export function SellerReviewsSection({
  sellerId,
  summary,
  reviews,
  questions,
  claimed,
  signedIn,
  canModerate,
}: {
  sellerId: string;
  summary: SellerSummary;
  /** Null when the reviews could not be loaded. */
  reviews: SellerReview[] | null;
  /** Null when the questions could not be loaded. */
  questions: Question[] | null;
  claimed: boolean;
  signedIn: boolean;
  canModerate: boolean;
}) {
  const keywordId = useId();
  const tabsId = useId();
  const [stars, setStars] = useState<number[]>(ALL_STARS);
  const [keyword, setKeyword] = useState("");
  const [tab, setTab] = useState<Tab>("reviews");
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ reviews: null, questions: null });

  const bars = distributionBars(summary.rating_distribution);
  const visible = reviews === null ? [] : filterSellerReviews(reviews, { stars, keyword });
  const partial = reviews !== null && summary.review_count > reviews.length;
  const average = summary.overall_average;

  const toggleStar = (star: number) =>
    setStars((current) => (current.includes(star) ? current.filter((s) => s !== star) : [...current, star]));

  const selectTab = (next: Tab) => {
    setTab(next);
    tabRefs.current[next]?.focus();
  };

  const tabButton = (key: Tab, label: string) => (
    <button
      ref={(el) => {
        tabRefs.current[key] = el;
      }}
      type="button"
      role="tab"
      id={`${tabsId}-${key}`}
      aria-selected={tab === key}
      aria-controls={`${tabsId}-${key}-panel`}
      tabIndex={tab === key ? 0 : -1}
      onClick={() => setTab(key)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          selectTab(key === "reviews" ? "questions" : "reviews");
        }
      }}
      className={`cursor-pointer pb-1 ${FACE} text-[13px] leading-5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)] ${
        tab === key ? "text-[var(--accent-primary)]" : "text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
      }`}
    >
      {label}
    </button>
  );

  return (
    <section id="all-reviews" aria-labelledby={`${tabsId}-heading`} className="scroll-mt-24">
      <p className="flex items-center gap-1.5">
        <Star size={22} weight="fill" aria-hidden="true" className="text-[var(--accent-success)]" />
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          {average === null ? "—" : average.toFixed(1)}
        </span>
      </p>
      <h2 id={`${tabsId}-heading`} className={`mt-3 ${FACE} text-[13px] text-[var(--text-primary)]`}>
        All reviews
      </h2>
      <p className={`${FACE} text-[11px] text-[var(--text-secondary)]`}>
        {summary.review_count} {summary.review_count === 1 ? "review" : "reviews"}
      </p>

      <p className={`mt-4 flex gap-2 rounded-[8px] bg-[#bacce6] px-4 py-3 ${FACE} text-[14px] leading-[21px] text-[var(--text-primary)]`}>
        <Info size={16} aria-hidden="true" className="mt-[3px] shrink-0" />
        Reviews are the opinions of individual users and not of Bluntly.ph.
      </p>

      <fieldset className="mt-4 rounded-[var(--radius-sm)] border border-[#b3b3b3] px-6 py-5">
        <legend className="sr-only">Show reviews with</legend>
        <ul className="flex flex-col gap-3">
          {bars.map((bar) => {
            const checked = stars.includes(bar.star);
            return (
              <li key={bar.star}>
                <label className="flex cursor-pointer items-center gap-2">
                  {/* The frame's box: a light square with a dark tick. The native
                      input stays underneath, so keyboard and screen readers get a
                      real checkbox. */}
                  <span className="relative grid h-4 w-4 shrink-0 place-items-center">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleStar(bar.star)}
                      className="peer absolute inset-0 m-0 cursor-pointer appearance-none rounded-[2px] border border-[var(--text-primary)] bg-[var(--surface-card)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
                    />
                    <Check
                      size={12}
                      weight="bold"
                      aria-hidden="true"
                      className="pointer-events-none relative hidden text-[var(--text-primary)] peer-checked:block"
                    />
                  </span>
                  <span className={`w-[38px] shrink-0 ${FACE} text-[11px] text-[var(--text-primary)]`}>
                    {bar.star} star
                  </span>
                  <span className="h-3 flex-1 overflow-hidden rounded-full bg-[var(--base-gray-200)]">
                    <span
                      className="block h-full rounded-full"
                      style={{ width: `${bar.share * 100}%`, background: STAR_BAR_COLOUR[bar.star] }}
                    />
                  </span>
                  <span className={`w-[34px] shrink-0 text-right ${FACE} text-[10px] text-[var(--text-primary)]`}>
                    {sharePercent(bar.share)}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </fieldset>

      <div className="relative mt-4">
        <label htmlFor={keywordId} className="sr-only">
          Search reviews by keyword
        </label>
        <MagnifyingGlass
          size={16}
          aria-hidden="true"
          className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]"
        />
        <input
          id={keywordId}
          type="search"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Search by keyword"
          className={`h-8 w-full rounded-[var(--radius-pill)] border border-[var(--text-primary)] bg-transparent pl-10 pr-4 ${FACE} text-[16px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus-visible:border-[var(--accent-primary)]`}
        />
      </div>

      {/* A 2px full-bleed rule under the tabs, as on the search page's frames. */}
      <div
        role="tablist"
        aria-label="Store content"
        className="-mx-4 mt-4 flex gap-8 border-b-2 border-[var(--base-gray-150)] px-4"
      >
        {tabButton("reviews", "Reviews")}
        {tabButton("questions", "Questions")}
      </div>

      <div
        role="tabpanel"
        id={`${tabsId}-reviews-panel`}
        aria-labelledby={`${tabsId}-reviews`}
        hidden={tab !== "reviews"}
        className="mt-6"
      >
        {reviews === null ? (
          <p className={`${FACE} text-[14px] text-[var(--text-secondary)]`}>
            Reviews could not be loaded right now.
          </p>
        ) : reviews.length === 0 ? (
          <p className={`${FACE} text-[14px] text-[var(--text-secondary)]`}>
            Nobody has rated this seller yet.{" "}
            <Link href={`/sellers/rate?seller=${sellerId}`} className="text-[var(--accent-primary)]">
              Be the first
            </Link>
            .
          </p>
        ) : (
          <>
            <p aria-live="polite" className={`${FACE} text-[12px] text-[var(--text-secondary)]`}>
              {visible.length === reviews.length && !partial
                ? `${visible.length} ${visible.length === 1 ? "review" : "reviews"}`
                : `${visible.length} of ${partial ? `the newest ${reviews.length}` : reviews.length} reviews`}
            </p>
            {visible.length === 0 ? (
              <p className={`mt-4 ${FACE} text-[14px] text-[var(--text-secondary)]`}>
                No reviews match. Tick more stars or change the keyword.
              </p>
            ) : (
              <ul className="mt-4 flex flex-col gap-8">
                {visible.map((review) => (
                  <SellerReviewCard key={review.id} review={review} canModerate={canModerate} />
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      <div
        role="tabpanel"
        id={`${tabsId}-questions-panel`}
        aria-labelledby={`${tabsId}-questions`}
        hidden={tab !== "questions"}
        className="mt-6"
      >
        <p className={`${FACE} text-[13px] text-[var(--text-secondary)]`}>
          {claimed
            ? "Ask the store directly. Its replies carry the Claimed Profile mark."
            : "Nobody has claimed this store yet, so other buyers are the ones who can answer."}
        </p>
        <AskSellerQuestionForm sellerId={sellerId} signedIn={signedIn} />
        {questions === null ? (
          <p className={`mt-4 ${FACE} text-[14px] text-[var(--text-secondary)]`}>
            Questions could not be loaded right now.
          </p>
        ) : questions.length === 0 ? (
          <p className={`mt-4 ${FACE} text-[14px] text-[var(--text-secondary)]`}>No questions yet.</p>
        ) : (
          // "Seller Page - Questions.png": the asker's 36px disc with "name •
          // shield score • level" and the age under it, then the question in
          // 14px bold. NOT RENDERED: the vote / Reply / Share row and the store's
          // nested reply — the list API carries no answers, so each question links
          // to its own page, where the store's reply is shown.
          <ul className="mt-6 flex flex-col gap-8">
            {questions.map((q) => {
              const asker = q.asker?.username ?? q.asker?.display_name ?? "A buyer";
              return (
                <li key={q.id}>
                  <Link href={`/questions/${q.id}`} className="block no-underline">
                    <span className="flex items-center gap-[9px]">
                      <ReviewerInitial name={asker} />
                      <span className={`min-w-0 ${FACE}`}>
                        <span className="flex flex-wrap items-center gap-x-1 text-[13px] text-[var(--text-primary)]">
                          <span className="truncate">{asker}</span>
                          {q.asker ? (
                            <>
                              <span aria-hidden="true" className="text-[var(--text-muted)]">
                                •
                              </span>
                              <TrustBadge
                                levelName={q.asker.trust_level_name}
                                stage={q.asker.trust_stage}
                                score={q.asker.reputation_score}
                                plain
                                compact
                              />
                              {q.asker.trust_level_name ? (
                                <>
                                  <span aria-hidden="true" className="text-[var(--text-muted)]">
                                    •
                                  </span>
                                  <span aria-hidden="true">{q.asker.trust_level_name}</span>
                                </>
                              ) : null}
                            </>
                          ) : null}
                        </span>
                        <span className="block text-[11px] text-[var(--text-secondary)]">
                          <time dateTime={q.created_at}>{shortAge(q.created_at)}</time>
                        </span>
                      </span>
                    </span>
                    <span className="mt-3 block text-[14px] font-bold leading-5 text-[var(--text-primary)]">
                      {q.body}
                    </span>
                    <span className={`mt-1 block ${FACE} text-[13px] text-[var(--text-secondary)]`}>
                      {q.answer_count} {q.answer_count === 1 ? "answer" : "answers"}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}

export default SellerReviewsSection;
