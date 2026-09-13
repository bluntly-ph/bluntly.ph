import Image from "next/image";

import { SimpleBunbunMark } from "@/components/reviews/SimpleBunbunMark";

/**
 * Bunbun asking the reviewer the question a step is really about.
 *
 * The composer's step references draw the mascot beside a speech bubble — the
 * heading states the topic ("Your verdict"), and Bunbun asks the actual question
 * ("Would you recommend this to a friend?"). Without it the step reads as a bare
 * form; with it, it reads as being asked something.
 *
 * TWO TREATMENTS, and the references decide which:
 *
 *   "simple"   the flat orange silhouette, composed from the owner's three
 *              primitives (see SimpleBunbunMark). Used while the step is still
 *              unanswered.
 *   "detailed" the full illustration, 504-BUNBUN-BASIC-NEUTRAL.svg from the
 *              authorized asset pack. Used once the reader has answered and the
 *              mascot reacts.
 *
 * That mapping is measured, not assumed. A connected-component pass over the
 * reference frames finds the three exact primitives in Reviewer step 2, step 2.1,
 * step 5 and step 5.1 — and NOT in step 2.2, which is the frame where a verdict
 * has been chosen and Bunbun asks "mind telling us why?". So the silhouette is
 * the idle state and the illustration is the reaction.
 *
 * Decorative: the question is real text in the bubble, so the image itself is
 * `alt=""` and hidden from assistive tech rather than described twice.
 */
export type MascotVariant = "simple" | "detailed";

export function MascotPrompt({
  children,
  variant = "simple",
  className = "",
}: {
  children: React.ReactNode;
  /** Which treatment the corresponding reference frame draws. */
  variant?: MascotVariant;
  className?: string;
}) {
  return (
    <div className={`flex items-end gap-1 ${className}`}>
      {variant === "simple" ? (
        // 63x60 native; the reference draws it unscaled beside the bubble.
        <SimpleBunbunMark className="mb-1" />
      ) : (
        <Image
          src="/mascots/bunbun-neutral.svg"
          alt=""
          aria-hidden="true"
          width={72}
          height={116}
          // 7122x11465 artwork; the height here is what the reference shows
          // beside the bubble, and the width follows the ratio.
          className="h-[116px] w-auto shrink-0 select-none"
          priority={false}
        />
      )}
      {/* The bubble sits above the mascot's head with a tail pointing back down
          at it, as drawn. `-translate-y` lifts it clear of the feet. */}
      <div className="relative -translate-y-6 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-4 py-3 shadow-[var(--shadow-card)]">
        <p className="text-[15px] leading-snug text-[var(--text-primary)]">{children}</p>
        <span
          aria-hidden="true"
          className="absolute -bottom-[7px] left-3 h-4 w-4 rotate-45 rounded-[3px] bg-[var(--surface-card)]"
        />
      </div>
    </div>
  );
}

export default MascotPrompt;
