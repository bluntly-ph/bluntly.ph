/**
 * The `bluntly` wordmark — the real artwork from the Figma file.
 *
 * The exported asset is a single near-white PNG (1024x316) with alpha. Rather
 * than shipping a second dark copy, it is used as a CSS mask so the mark paints
 * in `currentColor`: white on the auth gradient, ink on the light app surface,
 * brand orange where the design calls for it. One asset, every surface, and it
 * can never drift out of sync with itself.
 *
 * It is decorative-by-default here because the surrounding link supplies the
 * accessible name; pass `label` when the mark stands alone.
 */

const ASPECT = 1024 / 316;

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
        WebkitMaskImage: "url(/bluntly-logo.png)",
        maskImage: "url(/bluntly-logo.png)",
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
