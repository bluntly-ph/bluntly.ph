/**
 * The `bluntly` wordmark.
 *
 * Owner decision: the lowercase `bluntly` wordmark everywhere. The desktop
 * frames use a `bluntly.ph` lockup with a checkmark mark; that variant is
 * deliberately not implemented (docs/DEVIATIONS.md #61).
 *
 * Drawn as text rather than the design system's PNG so it stays crisp at any
 * size, recolours with the theme, and is selectable and readable by assistive
 * tech without alt-text duplication.
 */

export type LogoProps = {
  /** Rendered size in px. The wordmark is set at this cap height. */
  size?: number;
  /** Force a colour; defaults to inheriting the current text colour. */
  tone?: "brand" | "inherit";
  className?: string;
};

export function Logo({ size = 24, tone = "brand", className = "" }: LogoProps) {
  return (
    <span
      className={[
        "inline-flex select-none items-baseline",
        "font-[family-name:var(--font-body)] font-semibold tracking-[-0.02em]",
        tone === "brand" ? "text-[var(--accent-primary)]" : "",
        className,
      ].join(" ")}
      style={{ fontSize: `${size}px`, lineHeight: 1 }}
    >
      bluntly
    </span>
  );
}

export default Logo;
