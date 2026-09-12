import Image from "next/image";

/**
 * Bunbun asking the reviewer the question a step is really about.
 *
 * The composer's step references draw the mascot beside a speech bubble — the
 * heading states the topic ("Your verdict"), and Bunbun asks the actual question
 * ("Would you recommend this to a friend?"). Without it the step reads as a bare
 * form; with it, it reads as being asked something.
 *
 * The artwork is the owner's own export (`5. Bunbun different expressions/
 * 504-BUNBUN-BASIC-NEUTRAL.svg`), copied into `public/mascots/` — a real design
 * asset, not a crop of a mockup. It is pure vector at 24KB, so it stays sharp at
 * any size and costs less than the PNG it replaces would have.
 *
 * Decorative: the question is real text in the bubble, so the image itself is
 * `alt=""` and hidden from assistive tech rather than described twice.
 */
export function MascotPrompt({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-end gap-1 ${className}`}>
      <Image
        src="/mascots/bunbun-neutral.svg"
        alt=""
        aria-hidden="true"
        width={72}
        height={116}
        // 7122x11465 artwork; the height here is what the reference shows beside
        // the bubble, and the width follows the ratio.
        className="h-[116px] w-auto shrink-0 select-none"
        priority={false}
      />
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
