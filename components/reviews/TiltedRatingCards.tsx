import { Star } from "@phosphor-icons/react/dist/ssr";

/**
 * The tilted rating cards the composer frames scatter behind their content:
 * blank cards in the page colour that read only through the card shadow, each
 * carrying a row of 16px stars in the rating ladder's colours (#34ca43 green,
 * #fac800 yellow, #ff543e coral — read from the frames' star assets).
 *
 * Coordinates are a 390-wide frame's. A card that runs off the right edge is
 * anchored to that edge, so a wider phone still shows the sliver the frame
 * shows instead of pulling the card into view. MOBILE ONLY at every call site:
 * no desktop frame places them. Decorative, hidden from assistive tech and
 * unclickable.
 */
export type TiltedCard = {
  /** Frame x of the unrotated card. */
  x: number;
  /** Distance from the top of the decor box… */
  top?: number;
  /** …or from its bottom. */
  bottom?: number;
  w?: number;
  h?: number;
  /** Degrees. The frames use 5, -5 and -10. */
  tilt: number;
  /** One colour per star, left to right. */
  stars: string[];
  /** Card face at 70%, as the Find and All done frames draw it. */
  faded?: boolean;
  /** Runs off the right edge of the frame. */
  anchorRight?: boolean;
  /** Stars against the left edge instead of the right. */
  starsStart?: boolean;
};

const FRAME_W = 390;

export const STAR_GREEN = "var(--semantic-success-500)";
export const STAR_YELLOW = "var(--semantic-star)";
export const STAR_CORAL = "var(--brand-coral)";

/** The frames draw some coral and yellow stars at 70%. */
export function fadedStar(color: string): string {
  return `color-mix(in srgb, ${color} 70%, transparent)`;
}

export function starRow(count: number, color: string): string[] {
  return Array.from({ length: count }, () => color);
}

/**
 * "Reviewer Page - All done" (4550:8882) and "Seller Review - All done"
 * (4652:12914) place the same six, measured from the frame's bottom edge.
 */
export const DONE_CARDS: TiltedCard[] = [
  { x: -144, bottom: 5, tilt: 5, faded: true, stars: starRow(5, STAR_GREEN) },
  { x: -127, bottom: 60, tilt: 5, faded: true, stars: starRow(4, STAR_GREEN) },
  { x: -110, bottom: 115, tilt: 5, faded: true, stars: starRow(2, fadedStar(STAR_CORAL)) },
  { x: 376, bottom: 78, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(5, STAR_GREEN) },
  { x: 359, bottom: 133, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(4, STAR_GREEN) },
  { x: 343, bottom: 188, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(3, fadedStar(STAR_YELLOW)) },
];

export function TiltedRatingCards({ cards, className }: { cards: TiltedCard[]; className: string }) {
  return (
    <span aria-hidden="true" className={`pointer-events-none select-none overflow-hidden ${className}`}>
      {cards.map((card, i) => {
        const w = card.w ?? 185;
        const h = card.h ?? 95;
        return (
          <span
            key={i}
            className={`absolute flex items-end p-4 ${card.starsStart ? "justify-start" : "justify-end"}`}
            style={{
              width: w,
              height: h,
              top: card.top,
              bottom: card.bottom,
              ...(card.anchorRight ? { right: FRAME_W - card.x - w } : { left: card.x }),
              transform: `rotate(${card.tilt}deg)`,
            }}
          >
            <span
              className={`absolute inset-0 rounded-[12px] bg-[var(--surface-app)] shadow-[var(--shadow-card)] ${
                card.faded ? "opacity-70" : ""
              }`}
            />
            <span className="relative flex">
              {card.stars.map((color, s) => (
                <Star key={s} size={16} weight="fill" style={{ color }} />
              ))}
            </span>
          </span>
        );
      })}
    </span>
  );
}

export default TiltedRatingCards;
