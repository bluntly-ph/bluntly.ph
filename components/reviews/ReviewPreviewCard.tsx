import Image from "next/image";
import { ArrowFatUp, DotOutline, DotsThree, ImageSquare } from "@phosphor-icons/react/dist/ssr";

/**
 * "This is what people see first" — the live preview of the review card, on
 * step 7 and on the All done screen.
 *
 * Figma "ReviewCard" (7082:1414) with Media and Stats on, as placed in
 * "Reviewer Page - Step 7" (4452:748) and "Reviewer Page - All done" (4550:8882),
 * read 2026-09-15. The same tilted stack as the landing card: three 358x172
 * layers — the brand tint at 10% rotated +5deg, the tint flat, and the card
 * rotated -5deg in --surface-app with the warm #bcaca6 shadow — and inside,
 * 12px padding and a 12px gap between the body and a 100px media square at
 * radius 16. The body: a 28px avatar and the handle in 12px Light, the age in
 * 10px ExtraLight; the headline in 12px Bold; the stats — a 16px ArrowFatUp in
 * the success green, counts in 12px Light split by a 12px DotOutline. A 24px
 * DotsThree sits 12px from the top right.
 *
 * Bound to the draft: typing the title rewrites the headline, and the photo is
 * the one from step 6.
 *
 * INTENTIONAL PRODUCT DIFFERENCE: the frames fill the card with sample
 * engagement — an Honesty Score of 100, "5h", "14.8k", "3.2k comments" — and
 * float two pills over it, "Earned P45.50 today" and a reader's question. This
 * review has not been published, so it has no votes, comments, earnings or
 * questions; the counters show their real zero, the age says "now", and the
 * pills are not drawn. The reviewer's score is not in the composer's session
 * data, so the shield is left out rather than shown with a made-up number.
 */
export function ReviewPreviewCard({
  username,
  avatarUrl,
  productName,
  title,
  photoUrl,
  className = "mt-10",
}: {
  username: string | null;
  avatarUrl: string | null;
  productName: string | null;
  title: string;
  photoUrl: string | null;
  className?: string;
}) {
  const trimmed = title.trim();
  // The group reaches 9px into the left gutter, so it is 9px wider than the
  // column; the layers take that width less the 9px, which is 358px at 390 and
  // narrows with a 360 or 375px phone instead of running off the right edge.
  const layer = "absolute h-[172px] w-[calc(100%-9px)] rounded-[12px] bg-[rgba(239,88,33,0.1)]";

  return (
    // The frames place this group 9px left of the content edge.
    <div className={`relative -ml-[9px] h-[209px] ${className}`}>
      <div aria-hidden="true" className={`${layer} left-[11px] top-[21px] rotate-[5deg]`} />
      <div aria-hidden="true" className={`${layer} left-[11px] top-5`} />

      <div className="absolute left-[7px] top-[15px] flex h-[172px] w-[calc(100%-9px)] -rotate-[5deg] items-center gap-3 overflow-hidden rounded-[12px] bg-[var(--surface-app)] p-3 text-[var(--text-primary)] shadow-[0px_4px_4px_0px_#bcaca6]">
        <div className="flex min-w-0 flex-1 flex-col gap-2 self-stretch overflow-hidden">
          <div className="flex items-center gap-2">
            <span className="relative h-7 w-7 shrink-0 overflow-hidden rounded-full bg-[var(--base-gray-200)]">
              {avatarUrl ? <Image src={avatarUrl} alt="" fill sizes="28px" className="object-cover" /> : null}
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-[12px] font-light leading-4">{username ?? "you"}</span>
              <span className="text-[10px] font-extralight leading-[15px]">now</span>
            </span>
          </div>

          <p className="line-clamp-3 text-[12px] font-bold leading-[18px]">
            {productName ? `${productName} - ` : ""}
            {trimmed || "Your interesting title here..."}
          </p>

          <p className="flex items-center gap-[3px] text-[12px] font-light leading-none">
            <ArrowFatUp size={16} weight="fill" aria-hidden="true" className="text-[var(--accent-success)]" />
            0
            <DotOutline size={12} aria-hidden="true" className="text-[var(--base-gray-400)]" />0 comments
          </p>
        </div>

        <span className="relative grid h-[100px] w-[100px] shrink-0 place-items-center overflow-hidden rounded-[16px] bg-[#e1e1e1]">
          {photoUrl ? (
            <Image src={photoUrl} alt="" fill sizes="100px" className="object-cover" />
          ) : (
            <ImageSquare size={28} weight="light" aria-hidden="true" className="text-[var(--base-gray-400)]" />
          )}
        </span>

        {/* Drawn, not wired: there is nothing yet for a menu to act on. */}
        <DotsThree size={24} aria-hidden="true" className="absolute right-3 top-3" />
      </div>
    </div>
  );
}

export default ReviewPreviewCard;
