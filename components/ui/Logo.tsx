/**
 * The `bluntly` wordmark — the owner's own vector artwork.
 *
 * Now `UPDATED-MAIN-LOGO.svg` from the design asset pack, replacing the
 * 1024x316 PNG this used to mask. Same wordmark (the painted ratio measures
 * 3.2666 against the PNG's 3.2405) but real curves, so it stays sharp at any
 * size and on any display density instead of resampling a bitmap. The source
 * file insets the mark inside an 8000x4500 artboard; the copy in `public/` has
 * its viewBox retargeted to the painted mark so the artwork fills its box.
 *
 * It is still used as a CSS mask rather than an <img>, which is what lets it
 * paint in `currentColor`: white on the auth gradient, ink on the light app
 * surface, brand orange where the design calls for it. One asset, every
 * surface, and it can never drift out of sync with itself.
 *
 * It is decorative-by-default here because the surrounding link supplies the
 * accessible name; pass `label` when the mark stands alone.
 *
 * `public/bluntly-logo.png` stays even though the web UI no longer uses it:
 * `backend/app/adapters/email_templates.py` links it as `_LOGO_URL`, and mail
 * clients do not render SVG. Do not delete it as dead weight.
 */

/** The trimmed viewBox: 6481 x 1984. */
const ASPECT = 6481 / 1984;

export type LogoProps = {
  /** Rendered height in px. Width follows the artwork's aspect ratio. */
  height?: number;
  /** Accessible name. Omit when an ancestor link/button already names it. */
  label?: string;
  className?: string;
};

export function Logo({ height = 24, label, className = "" }: LogoProps) {
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={`inline-block shrink-0 bg-current ${className}`}
      style={{
        height: `${height}px`,
        width: `${Math.round(height * ASPECT)}px`,
        WebkitMaskImage: "url(/bluntly-logo.svg)",
        maskImage: "url(/bluntly-logo.svg)",
        WebkitMaskRepeat: "no-repeat",
        maskRepeat: "no-repeat",
        WebkitMaskSize: "contain",
        maskSize: "contain",
        WebkitMaskPosition: "center",
        maskPosition: "center",
      }}
    />
  );
}

export default Logo;
