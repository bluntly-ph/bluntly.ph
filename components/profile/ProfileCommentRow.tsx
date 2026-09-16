import Link from "next/link";
import { ArrowFatUp, ChatsCircle } from "@phosphor-icons/react/dist/ssr";

import type { AuthoredComment } from "@/lib/comments";
import { compactCount } from "@/lib/dashboard";
import { splitHeadline } from "@/lib/reviews";

/**
 * One of a member's comments in their profile's Comments tab: Figma
 * "Profile Page - Comments" (5446:6398), read 2026-09-16. A 358px column: the
 * review's headline in 14px with the product Bold and the rest Regular, the
 * comment itself 4px under it in 12px Light, then a 32px row with the
 * engagement counts — a 16px glyph 4px before a 12px number. A full-bleed
 * hairline closes the row.
 *
 * INTENTIONAL PRODUCT DIFFERENCE: the frame's Eye/views count is not drawn. No
 * view count is served for a review on any read path (the Reviews tab drops the
 * same pill for the same reason), and inventing one would be fabricating a
 * statistic. The upvote and reply counts are the review's, as the frame shows
 * them — the row is a way back into that conversation, not a scoreboard for the
 * comment.
 *
 * From `md` the tab is a two-column grid, so each comment becomes its own white
 * card, matching how ProfileReviewCard widens.
 */
export function ProfileCommentRow({ comment }: { comment: AuthoredComment }) {
  const headline = splitHeadline(comment.review.title, comment.review.product_name);

  return (
    <li className="border-b border-[var(--line-hairline-10)] px-4 py-4 md:rounded-[16px] md:border-b-0 md:bg-[var(--surface-card)] md:p-4 md:shadow-[var(--shadow-card)]">
      <article className="mx-auto w-full max-w-[358px] md:max-w-none">
        <Link
          href={`/reviews/${comment.review.id}`}
          className="block text-[var(--text-primary)] no-underline"
        >
          <h2 className="text-[14px] leading-[21px]">
            {headline.product ? (
              <>
                <span className="font-bold">{headline.product} - </span>
                {headline.rest}
              </>
            ) : (
              <span className="font-bold">{comment.review.title}</span>
            )}
          </h2>
          <p className="mt-1 text-[12px] font-light leading-[18px]">{comment.body}</p>
        </Link>

        <div className="mt-1 flex h-8 items-center justify-end gap-3">
          <span className="inline-flex items-center gap-1 text-[12px] font-light leading-none text-[var(--text-primary)]">
            <ArrowFatUp
              size={16}
              weight="fill"
              aria-hidden="true"
              className="text-[var(--accent-success)]"
            />
            {compactCount(comment.review.helpful_votes)}
            <span className="sr-only"> found this review helpful</span>
          </span>
          <span className="inline-flex items-center gap-1 text-[12px] leading-none text-[var(--text-primary)]">
            <ChatsCircle size={16} aria-hidden="true" />
            {compactCount(comment.review.comment_count)}
            <span className="sr-only">
              {comment.review.comment_count === 1 ? " comment" : " comments"}
            </span>
          </span>
        </div>
      </article>
    </li>
  );
}

export default ProfileCommentRow;
