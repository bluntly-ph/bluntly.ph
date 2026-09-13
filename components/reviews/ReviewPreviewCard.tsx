import Image from "next/image";
import { ArrowFatUp, ShieldCheck } from "@phosphor-icons/react/dist/ssr";

/**
 * "This is what people see first" — step 7's live preview of the review card.
 *
 * Measured from "Reviewer Page - Step 7.png" and "7.1.png" at 390. Typing in
 * the title field rewrites the card's headline in both frames, so this is a
 * live preview bound to the draft, not a static illustration.
 *
 *   white card   x16..372, ~356x158, rotated about -4deg (its bottom edge
 *                falls 14px across 160px of width), page-coloured with the
 *                card shadow, 16px radius
 *   peach card   the same box behind it, tilted the other way, rgb(242,227,220)
 *   avatar       34px circle, top left
 *   shield       12x13 at rgb(55,113,200) — accent-trust, to the unit
 *   headline     bold, two lines, "<product> - <the title being typed>"
 *   upvote arrow 13x13 at rgb(31,175,56) — accent-success, to the unit
 *   thumb        ~105px square on the right, 12px radius: the step 6 photo
 *
 * WHAT IS NOT COPIED FROM THE FRAME, and why:
 *
 * The frame fills the card with sample engagement — "100" beside the name,
 * "5h", "14.8k", "3.2k comments" — and floats two pills over it, "Earned
 * P45.50 today" and a quoted question that changes between the two frames
 * ("How noisy is it?" -> "Nice review!"). Those are mock data. This review has
 * not been submitted, so it has no votes, no comments, no age and no
 * earnings, and putting a peso figure on the reviewer's own screen would be
 * stating something untrue rather than styling something true.
 *
 * So the card is 1:1 in layout and bound to what the reviewer actually has —
 * their name, avatar, product, title and photo — with the counters at their
 * real values and the two pills left out. Everything else here is the frame's.
 * If the owner wants the pills back as decoration, they are a few lines.
 */
export function ReviewPreviewCard({
  username,
  avatarUrl,
  productName,
  title,
  photoUrl,
}: {
  username: string | null;
  avatarUrl: string | null;
  productName: string | null;
  title: string;
  photoUrl: string | null;
}) {
  const headline = [productName, title.trim()].filter(Boolean).join(" – ");

  return (
    <div className="relative mt-10 h-[190px]">
      {/* The tilted card peeking out behind, top-left and bottom-right. */}
      <span
        aria-hidden="true"
        className="absolute inset-x-0 top-[6px] h-[158px] rotate-[3deg] rounded-[var(--radius-md)] bg-[rgb(242,227,220)]"
      />

      <div className="absolute inset-x-0 top-0 h-[158px] -rotate-[4deg] rounded-[var(--radius-md)] bg-[var(--surface-app)] p-4 shadow-[var(--shadow-card)]">
        <div className="flex gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="relative h-[34px] w-[34px] shrink-0 overflow-hidden rounded-full bg-[var(--base-gray-200)]">
                {avatarUrl ? (
                  <Image src={avatarUrl} alt="" fill sizes="34px" className="object-cover" />
                ) : null}
              </span>
              <span className="truncate text-[14px] font-medium text-[var(--text-primary)]">
                {username ?? "you"}
              </span>
              <span aria-hidden="true" className="text-[var(--text-muted)]">
                &middot;
              </span>
              <ShieldCheck
                size={13}
                weight="fill"
                aria-hidden="true"
                className="shrink-0 text-[var(--accent-trust)]"
              />
              <span className="text-[12px] text-[var(--text-secondary)]">now</span>
            </div>

            <p className="mt-2 line-clamp-2 text-[15px] font-bold leading-[20px] text-[var(--text-primary)]">
              {headline || "Your interesting title here…"}
            </p>

            <p className="mt-2 flex items-center gap-1.5 text-[13px] text-[var(--text-primary)]">
              <ArrowFatUp
                size={13}
                weight="fill"
                aria-hidden="true"
                className="text-[var(--accent-success)]"
              />
              0
              <span aria-hidden="true" className="text-[var(--text-muted)]">
                &middot;
              </span>
              0 comments
            </p>
          </div>

          <span className="relative h-[105px] w-[105px] shrink-0 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--base-gray-200)]">
            {photoUrl ? (
              <Image src={photoUrl} alt="" fill sizes="105px" className="object-cover" />
            ) : null}
          </span>
        </div>
      </div>
    </div>
  );
}

export default ReviewPreviewCard;
