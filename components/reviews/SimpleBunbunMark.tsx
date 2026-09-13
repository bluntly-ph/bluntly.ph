import Image from "next/image";

/**
 * The simplified Bunbun silhouette.
 *
 * NOT a flat image and NOT the detailed illustration — it is three owner-drawn
 * primitives composed into one shape:
 *
 *   public/mascots/simple-bunbun/vertical.png   from "Rectangle 149.png"  30x60
 *   public/mascots/simple-bunbun/base.png       from "Rectangle 148.png"  57x30
 *   public/mascots/simple-bunbun/accent.png     from "Rectangle 146.png"   9x6
 *
 * The offsets below were measured from the reference screenshots rather than
 * guessed: a connected-component pass over each frame located the pieces by
 * their exact colours and sizes, and every frame that uses the silhouette
 * (Reviewer step 2 and 2.1, step 5 and 5.1, "Let's talk money" x2, and the
 * Question audience chooser) places them at the SAME relative offsets, at
 * native scale with no scaling:
 *
 *              x    y     w   h
 *   vertical   24    0    30  60      painted first
 *   base        0   30    57  30      paints OVER the vertical's lower half
 *   accent     54   21     9   6
 *   bounds                 63  60
 *
 * The vertical piece is the same brand orange at alpha 204, which is what makes
 * it read lighter than the base — it is the file's own alpha, not a tint applied
 * here, so nothing is recoloured.
 *
 * Decorative by default: wherever this is used, a speech bubble carries the real
 * text. `scale` multiplies the native 63x60 for surfaces that need it larger.
 */

const NATIVE_W = 63;
const NATIVE_H = 60;

/** [src, alt-less piece, x, y, w, h] at native scale. */
const PIECES = [
  { src: "/mascots/simple-bunbun/vertical.png", x: 24, y: 0, w: 30, h: 60 },
  { src: "/mascots/simple-bunbun/base.png", x: 0, y: 30, w: 57, h: 30 },
  { src: "/mascots/simple-bunbun/accent.png", x: 54, y: 21, w: 9, h: 6 },
] as const;

export function SimpleBunbunMark({
  scale = 1,
  className = "",
}: {
  scale?: number;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={`relative block shrink-0 select-none ${className}`}
      style={{ width: NATIVE_W * scale, height: NATIVE_H * scale }}
    >
      {PIECES.map((p) => (
        <Image
          key={p.src}
          src={p.src}
          alt=""
          width={p.w}
          height={p.h}
          // Native pixel art at these sizes — let the browser scale it only when
          // `scale` says so, and never resample it up by accident.
          className="absolute"
          style={{
            left: p.x * scale,
            top: p.y * scale,
            width: p.w * scale,
            height: p.h * scale,
          }}
          unoptimized
        />
      ))}
    </span>
  );
}

export default SimpleBunbunMark;
