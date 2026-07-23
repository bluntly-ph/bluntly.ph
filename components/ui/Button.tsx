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
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  icon = null,
  fullWidth = false,
  className = "",
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      disabled={disabled}
      className={[
        "inline-flex items-center justify-center gap-2 rounded-[var(--radius-pill)]",
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
      ].join(" ")}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}

export default Button;
