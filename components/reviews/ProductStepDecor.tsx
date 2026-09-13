import { Star } from "@phosphor-icons/react/dist/ssr";

/**
 * The floating rating cards behind the product step.
 *
 * The reference drops three tilted cards around the empty state, each showing
 * only a row of stars. They are ordinary primitives — a rounded surface, a soft
 * shadow, a few degrees of rotation and star glyphs — so they are built rather
 * than treated as missing artwork.
 *
 * Measured from "Reviewer Page - Step 1.png" at 390x844:
 *
 *   green stars  13x13  rgb(109,214,120)  x=51,67,83,99  y~789-793  (4, 16px pitch)
 *   red stars    13x13  rgb(251,132,116)  x=100,116      y~737-738  (2, 16px pitch)
 *   right cluster                          x~364-390, y~438 and ~495, clipped
 *
 * The rows drift about 4px over 48px, which is a tilt of roughly 5 degrees.
 *
 * MOBILE ONLY. Every position above is absolute within a 390-wide frame, and the
 * pack contains no desktop frame for this step — so rather than invent where
 * they belong on a 1440 canvas, they are drawn where the reference specifies and
 * omitted above `sm`. Purely decorative: hidden from assistive tech and
 * unclickable.
 */

const GREEN = "rgb(109,214,120)";
const RED = "rgb(251,132,116)";

function StarRow({ count, color }: { count: number; color: string }) {
  return (
    <span className="flex gap-[3px]">
      {Array.from({ length: count }, (_, i) => (
        <Star key={i} size={13} weight="fill" style={{ color }} />
      ))}
    </span>
  );
}

function Card({
  className,
  rotate,
  children,
}: {
  className: string;
  rotate: number;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`absolute rounded-[var(--radius-md)] bg-[var(--surface-card)] px-3 py-2.5 shadow-[var(--shadow-card)] ${className}`}
      style={{ transform: `rotate(${rotate}deg)` }}
    >
      {children}
    </span>
  );
}

export function ProductStepDecor() {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10 hidden select-none overflow-hidden max-sm:block"
    >
      {/* bottom-left pair: the red row sits above the green row, both tilted */}
      <Card className="left-[76px] top-[470px]" rotate={4}>
        <StarRow count={2} color={RED} />
      </Card>
      <Card className="left-[27px] top-[522px]" rotate={5}>
        <StarRow count={4} color={GREEN} />
      </Card>
      {/* right edge: deliberately runs past the viewport, as drawn */}
      <Card className="left-[340px] top-[170px]" rotate={-6}>
        <StarRow count={3} color={GREEN} />
      </Card>
    </span>
  );
}

export default ProductStepDecor;
