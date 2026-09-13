import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

/**
 * Pill button — the design's dominant CTA shape (32px radius, 56px tall).
 *
 * Variants are taken from the Login & Signup frames:
 *   primary   solid brand orange, white label            ("Send code", "Continue")
 *   onBrand   solid gray-100 on the gradient, ink label  ("Continue with Google")
 *   outline   transparent, 1px gray-100 border           ("Sign up with email")
 *   secondary transparent, ink hairline
 *
 * The disabled state is literal from the frames: rgba(32,32,32,.14) fill with
 * rgba(32,32,32,.52) label — not an opacity fade, which would tint the label
 * differently on the gradient.
 */

type Variant = "primary" | "onBrand" | "outline" | "secondary";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-[var(--accent-primary)] text-white hover:bg-[var(--accent-primary-strong)]",
  onBrand:
    "bg-[var(--base-gray-100)] text-[var(--text-primary)] hover:bg-white",
  outline:
    "bg-transparent text-[var(--base-gray-100)] border border-[var(--base-gray-100)] " +
    "hover:bg-[rgba(242,242,242,0.12)]",
  secondary:
    "bg-transparent text-[var(--text-primary)] " +
    "shadow-[inset_0_0_0_1px_var(--base-ink-800)] hover:bg-[var(--line-hairline-10)]",
};

const SIZES: Record<Size, string> = {
  sm: "text-[length:var(--text-xs)] px-4 py-[7px]",
  md: "text-[length:var(--text-md)] px-7 h-[var(--control-button-h)]",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  fullWidth?: boolean;
  /**
   * Render as a link instead of a button.
   *
   * Something that navigates should be an anchor. Wrapping this component in
   * `<Link className="contents">` instead nests a button inside an anchor,
   * which is invalid, and leaves the control with `cursor: default` — that is
   * QA-012, and it survived in five more places than the two QA reported.
   *
   * `CtaLink` is the other half of that fix and remains the right choice for a
   * standalone call to action. This exists for the cases where the pill has to
   * stay byte-identical to the button beside it: CtaLink's sizes are its own
   * (36/44px against this component's 31/56), and swapping one for the other
   * silently resizes the control — which is how the page-title CTAs grew from
   * a 31px chip to a 44px pill the last time QA-012 was fixed.
   */
  href?: string;
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  icon = null,
  fullWidth = false,
  className = "",
  disabled,
  href,
  ...rest
}: ButtonProps) {
  const classes = [
        // `cursor-pointer` (QA-012): a <button> renders with cursor:default,
        // so nothing about it said "clickable" until it was pressed.
        // `disabled:` is not decoration — this project has no tailwind-merge,
        // so conflicting utilities are settled by stylesheet order, and plain
        // `cursor-not-allowed` is emitted BEFORE `cursor-pointer` and loses.
        // The pseudo-class raises specificity to (0,0,2,0) and wins regardless.
        "inline-flex cursor-pointer items-center justify-center gap-2",
        "disabled:cursor-not-allowed",
        "rounded-[var(--radius-pill)]",
        "font-[family-name:var(--font-body)] font-semibold leading-none",
        "transition-[background-color,transform,border-color]",
        "duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
        // `active` covers pointer and touch; the design system's original used
        // onMouseDown, which never fires on a phone.
        "active:scale-[0.97] motion-reduce:active:scale-100",
        disabled
          ? "cursor-not-allowed border-transparent bg-[var(--disabled-surface)] " +
            "text-[var(--disabled-text)] active:scale-100"
          : VARIANTS[variant],
        SIZES[size],
        fullWidth ? "w-full" : "",
        className,
  ].join(" ");

  // A disabled link is not a thing the platform has, so a disabled Button
  // stays a <button> even when given an href — it cannot navigate anyway.
  if (href && !disabled) {
    return (
      <Link
        href={href}
        // Read by `.prose a:not([data-cta])`: without it a pill dropped into an
        // article inherits the prose link colour and loses its label.
        data-cta=""
        className={`${classes} no-underline`}
      >
        {icon}
        {children}
      </Link>
    );
  }

  return (
    <button disabled={disabled} className={classes} {...rest}>
      {icon}
      {children}
    </button>
  );
}

export default Button;
